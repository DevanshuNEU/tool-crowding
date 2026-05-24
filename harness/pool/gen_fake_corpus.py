#!/usr/bin/env python3
"""
Generator for design/fake_tool_corpus.jsonl for tool-crowding padded-N=1 control.
Method B per PADDING_STRATEGY.md §3 (LLM-authored entries, deterministic seed,
passed through code-domain leakage QA gate and JSON Schema validity gate).

Run from anywhere:
    python3 harness/pool/gen_fake_corpus.py
"""
import json, hashlib, random, re, sys, os
from collections import Counter
from pathlib import Path

import tiktoken
ENC = tiktoken.get_encoding("cl100k_base")

SEED = "tool-crowding-padded-N1-corpus-v1-2026-05-23"
random.seed(SEED)

# ----------------------------------------------------------------------------
# QA gate: forbidden tokens (code-retrieval vocab) per PADDING_STRATEGY.md §3
# Expanded with the additional bans listed in the task prompt.
# ----------------------------------------------------------------------------
FORBIDDEN = re.compile(
    r"\b("
    r"code|coding|function|functional|file|files|repo|repos|repository|repositories|"
    r"github|gitlab|git|commit|branch|merge|"
    r"search|searching|grep|retriev|retrieval|index|indexing|snippet|snippets|"
    r"AST|syntax|parse|parser|parsing|compile|compiler|"
    r"variable|debug|debugger|library|libraries|"
    r"script|scripts|programming|developer|software|"
    r"scrape|scraping|scraper"
    r")\b",
    re.IGNORECASE,
)

# Real-server names to avoid (per SERVER_POOL.md)
SERVER_POOL_NAMES = {
    "filesystem", "memory", "sequential-thinking", "sequential_thinking",
    "time", "sqlite", "postgres", "postgresql", "brave-search", "bravesearch",
    "linear", "notion", "slack", "github", "git", "aider", "fetch", "oci",
    "opencodeintel",
}

def tok_count(description, schema):
    return len(ENC.encode(description + json.dumps(schema, sort_keys=False)))

def passes_qa(name, description, schema):
    blob = description + " " + name
    if FORBIDDEN.search(blob):
        m = FORBIDDEN.search(blob)
        return False, f"forbidden_vocab: '{m.group(0)}'"
    nname = name.lower().replace("_","").replace("-","")
    for sp in SERVER_POOL_NAMES:
        snorm = sp.replace("_","").replace("-","")
        if snorm == nname:
            return False, "name_collision_serverpool_exact"
        # substring guard for short distinctive server names
        if snorm in nname and len(snorm) >= 5:
            return False, f"name_collision_serverpool_substring:{snorm}"
    if not isinstance(schema, dict): return False, "schema_not_dict"
    if schema.get("type") != "object": return False, "schema_type"
    if "properties" not in schema: return False, "schema_no_props"
    return True, None

ENTRIES = []
def add(name, desc, schema, band):
    ENTRIES.append((name, desc, schema, band))

def sch_small(props):
    return {"type":"object","properties":props,"required":list(props.keys())[:1]}
def sch_med(props, required=None):
    return {"type":"object","properties":props,"required":required if required is not None else list(props.keys())[:2]}
def sch_large(props, required=None):
    return {"type":"object","properties":props,"required":required if required is not None else list(props.keys())[:3]}

S = {"type":"string"}
I = {"type":"integer"}
N = {"type":"number"}
B = {"type":"boolean"}
def E(opts): return {"type":"string","enum":opts}
def A(items): return {"type":"array","items":items}

# ============================================================================
# DOMAIN 1: TIME / TIMEZONE (note: Time MCP collision avoided via distinct names)
# ============================================================================
add("TimezoneShift","Convert a wall-clock instant from one IANA timezone to another, returning the localized result.",sch_med({"instant_iso":S,"source_zone":S,"target_zone":S}),"small")
add("DaylightSavingsLookup","Report whether a given date in a named region falls inside that region's daylight saving period and the UTC offset in effect.",sch_med({"date":S,"region":S}),"small")
add("BusinessHourOverlap","Given two named regions and their typical workday windows, compute the overlapping wall-clock window when both are open.",sch_med({"region_a":S,"region_b":S,"workday_start":S,"workday_end":S}),"medium")
add("WorldClockBoard","Return current local times across a list of named cities for a glanceable dashboard.",sch_small({"cities":A(S),"format_24h":B}),"small")
add("MeetingTimeProposer","Suggest up to five wall-clock meeting windows that fall within working hours in each participant's home timezone, with optional preference for mornings or afternoons.",sch_large({"participants":A({"type":"object","properties":{"name":S,"zone":S}}),"duration_minutes":I,"preferred_part_of_day":E(["morning","afternoon","evening","any"]),"earliest_date":S,"latest_date":S}),"large")
add("RelativeTimeDescriber","Render a human-friendly relative phrase such as 'in two hours' or 'yesterday afternoon' from an absolute timestamp.",sch_small({"timestamp_iso":S,"now_iso":S}),"small")
add("ZoneAbbreviationResolver","Disambiguate a colloquial timezone abbreviation such as CST to its canonical IANA identifier given a hint country.",sch_med({"abbreviation":S,"country_hint":S}),"small")

# ============================================================================
# DOMAIN 2: COLOR PALETTE / CONTRAST
# ============================================================================
add("ContrastRatioCalculator","Compute the WCAG 2.2 contrast ratio between a foreground and background hex color and report AA and AAA pass status for normal and large text sizes.",sch_med({"foreground_hex":S,"background_hex":S}),"medium")
add("ComplementaryPaletteGenerator","Generate a five-swatch palette around a seed color using complementary, analogous, or triadic harmony rules.",sch_med({"seed_hex":S,"harmony":E(["complementary","analogous","triadic","tetradic","monochromatic"])}),"medium")
add("ColorNameLookup","Return the closest named color from the CSS, Pantone, or RAL vocabulary for a given hex value.",sch_med({"hex":S,"vocabulary":E(["css","pantone","ral"])}),"small")
add("ColorBlindSimulator","Render how a hex color would appear under common color-vision deficiencies including deuteranopia, protanopia, and tritanopia.",sch_med({"hex":S,"deficiency":E(["deuteranopia","protanopia","tritanopia","achromatopsia"])}),"small")
add("HexToHslConverter","Convert a six-digit hex color into hue, saturation, and lightness components.",sch_small({"hex":S}),"small")
add("BrandPaletteAuditor","Audit a candidate brand palette of three to seven colors for internal contrast coverage, accessibility under three common color-vision deficiencies, and perceived warmth or coolness, returning a structured report with per-pair findings.",sch_large({"palette_hex":A(S),"intended_text_use":A(E(["body","headings","ui_controls","decorative"])),"include_deficiency_check":B}),"large")
add("GradientStopSuggester","Suggest gradient stops between two anchor colors using a chosen interpolation space such as Oklch or sRGB.",sch_med({"start_hex":S,"end_hex":S,"stops":I,"interpolation_space":E(["srgb","oklch","oklab","hsluv"])}),"medium")

# ============================================================================
# DOMAIN 3: WEATHER / CLIMATE
# ============================================================================
add("CurrentConditionsReporter","Return the present temperature, humidity, wind, and sky description for a named locality.",sch_med({"locality":S,"units":E(["metric","imperial"])}),"small")
add("HourlyForecastReader","Retrieve an hour-by-hour forecast over the next 48 hours for a named locality, including precipitation probability and felt temperature.",sch_med({"locality":S,"hours_ahead":I,"include_precip_probability":B}),"medium")
add("ClimateNormalsLookup","Look up the 30-year climate normals for a named locality and return monthly averages of temperature, precipitation, and sunshine hours.",sch_med({"locality":S,"month":E(["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec","all"])}),"medium")
add("AirQualityAdvisoryReader","Report the current air quality advisory and the dominant pollutant for a named locality, mapping to a colored caution level.",sch_med({"locality":S,"standard":E(["us_epa","eu_caqi","cn_haqi"])}),"small")
add("StormWarningChecker","Check whether any active severe-weather advisory is in force over a named locality and return the issuing authority and expiration time.",sch_med({"locality":S,"include_marine":B}),"small")
add("HistoricalWeatherReplay","Return the observed weather conditions on a specific past date at a named locality, including daily high, low, precipitation total, and dominant sky description, for use in retrospective planning narratives.",sch_large({"locality":S,"date":S,"include_hourly_breakdown":B,"units":E(["metric","imperial"])}),"large")
add("UvExposureAdvisor","Report the peak ultraviolet level for the day at a named locality and recommend a sun-exposure caution level.",sch_med({"locality":S,"skin_sensitivity":E(["low","medium","high"])}),"small")

# ============================================================================
# DOMAIN 4: RECIPE / NUTRITION
# ============================================================================
add("RecipeIngredientScaler","Scale every ingredient in a saved recipe up or down to a new serving size, preserving original ratios.",sch_med({"recipe_id":S,"new_servings":I}),"small")
add("NutritionFactsLookup","Return calories, macronutrients, and major micronutrients per 100 grams of a named whole or prepared food.",sch_med({"food_name":S,"include_micronutrients":B}),"medium")
add("RecipeSubstitutionAdvisor","Suggest acceptable substitutions for an ingredient given dietary constraints such as dairy-free, gluten-free, or nut-free, with notes on flavor and texture trade-offs.",sch_large({"original_ingredient":S,"dietary_constraints":A(E(["dairy_free","gluten_free","nut_free","vegan","vegetarian","kosher","halal","low_sodium"])),"preserve_role":E(["binder","leavening","fat","sweetener","flavor"])}),"large")
add("MealPlanCalorieBudgeter","Distribute a daily calorie target across breakfast, lunch, dinner, and an optional snack, given a chosen macronutrient split.",sch_med({"daily_calories":I,"macro_split":E(["balanced","high_protein","low_carb","mediterranean"]),"include_snack":B}),"medium")
add("CookingTemperatureGuide","Return the recommended internal cooking temperature for a named protein at a chosen doneness level.",sch_med({"protein":S,"doneness":E(["rare","medium_rare","medium","medium_well","well_done"])}),"small")
add("PantryRecipeSuggester","Suggest recipes that can be made from a provided pantry inventory, ranked by how few additional ingredients are needed and how well they match a chosen cuisine.",sch_large({"pantry_items":A(S),"cuisine_preference":E(["italian","mexican","japanese","indian","mediterranean","american","any"]),"max_missing_ingredients":I,"exclude_allergens":A(S)}),"large")
add("FoodPairingFlavorWheel","Suggest complementary ingredients for a seed ingredient using a flavor-affinity vocabulary.",sch_med({"seed_ingredient":S,"flavor_axis":E(["sweet","savory","umami","acidic","bitter"])}),"small")

# ============================================================================
# DOMAIN 5: MUSIC / PODCAST METADATA
# ============================================================================
add("TrackMetadataLookup","Return the title, artist, album, release year, and duration for a track identified by ISRC or by artist and title pair.",sch_med({"isrc":S,"artist":S,"title":S},required=[]),"medium")
add("AlbumTracklistReader","Read the ordered tracklist of a named album, with per-track duration and any featured-artist credits.",sch_med({"album_id":S,"include_features":B}),"small")
add("PodcastEpisodeSummarizer","Return the published title, host names, duration, and editorial summary of a named podcast episode.",sch_med({"podcast_name":S,"episode_title":S}),"medium")
add("GenreSimilarityExplorer","Suggest musical genres adjacent to a seed genre using a hand-curated affinity map, with optional restriction to currently-active scenes.",sch_large({"seed_genre":S,"depth":I,"exclude_subgenres":B,"active_scenes_only":B}),"medium")
add("ArtistDiscographyTimeline","Return a chronological list of an artist's studio albums with release year, label, and a one-line editorial note for each entry.",sch_med({"artist_name":S,"include_eps":B,"include_live_albums":B}),"medium")
add("BeatsPerMinuteEstimator","Estimate the tempo in beats per minute of a track from its uploaded audio fingerprint.",sch_med({"audio_fingerprint":S,"include_confidence":B}),"small")
add("PodcastChapterMarkerExtractor","Return the chapter markers and their start times for a podcast episode that publishes structured chapter metadata.",sch_small({"episode_id":S}),"small")

# ============================================================================
# DOMAIN 6: LANGUAGE / TRANSLATION
# ============================================================================
add("TextLanguageDetector","Detect the most likely natural language of a piece of text and return an ISO 639-1 tag plus confidence.",sch_small({"text":S}),"small")
add("PhraseTranslator","Translate a short phrase from a source language to a target language, with optional register hint such as formal or casual.",sch_med({"text":S,"source_lang":S,"target_lang":S,"register":E(["formal","neutral","casual"])}),"medium")
add("IdiomExplainer","Explain the literal and figurative meaning of an idiom in a named language and offer two equivalents in another language if any exist.",sch_med({"idiom":S,"source_lang":S,"target_lang":S}),"medium")
add("TransliterationConverter","Transliterate text between two writing systems for the same spoken language, for instance between Hiragana and Romaji.",sch_med({"text":S,"source_script":S,"target_script":S}),"small")
add("PronunciationGuide","Return an IPA pronunciation and an audio waveform reference for a word in a named language and regional accent.",sch_med({"word":S,"language":S,"accent_hint":S}),"small")
add("LanguageLearningFlashcardBuilder","Build a deck of spaced-repetition flashcards from a vocabulary list, with target language, source language, example sentences for each word, and an optional difficulty tier that tunes how many obscure entries are included.",sch_large({"vocab_list":A(S),"source_lang":S,"target_lang":S,"include_example_sentences":B,"difficulty_tier":E(["beginner","intermediate","advanced"])}),"large")

# ============================================================================
# DOMAIN 7: CURRENCY EXCHANGE / UNIT CONVERSION
# ============================================================================
add("CurrencyRateLookup","Return the spot mid-market exchange rate between two ISO 4217 currencies as of a chosen instant.",sch_med({"from_currency":S,"to_currency":S,"at_instant_iso":S}),"small")
add("LengthUnitConverter","Convert a numeric length between any two supported units across metric, imperial, and astronomical systems.",sch_med({"value":N,"from_unit":S,"to_unit":S}),"small")
add("MassUnitConverter","Convert a numeric mass between any two supported units across metric and imperial systems including troy ounces.",sch_med({"value":N,"from_unit":S,"to_unit":S}),"small")
add("TemperatureConverter","Convert a temperature between Celsius, Fahrenheit, Kelvin, and Rankine.",sch_med({"value":N,"from_unit":E(["C","F","K","R"]),"to_unit":E(["C","F","K","R"])}),"small")
add("VolumeUnitConverter","Convert a volume between metric, US customary, and imperial cooking units while flagging where US and imperial cups differ.",sch_med({"value":N,"from_unit":S,"to_unit":S,"system_hint":E(["us","imperial","metric"])}),"medium")
add("CurrencyHistoryChart","Return daily closing exchange rates between two currencies across a chosen date window for charting and trend description, with optional smoothing over a moving-average window in days.",sch_large({"from_currency":S,"to_currency":S,"start_date":S,"end_date":S,"moving_average_days":I}),"medium")
add("AnyUnitGeneralConverter","Attempt to convert between any two unit strings by routing through a dimensional analysis solver, returning either the result or a structured reason if the dimensions are incompatible.",sch_med({"value":N,"from_unit":S,"to_unit":S}),"medium")

# ============================================================================
# DOMAIN 8: SUNRISE / SUNSET / ASTRONOMY
# ============================================================================
add("SunriseSunsetLookup","Return the civil sunrise and sunset times for a given date at a chosen latitude and longitude.",sch_med({"date":S,"latitude":N,"longitude":N}),"small")
add("MoonPhaseReporter","Report the lunar phase, illumination percentage, and angular size on a given date.",sch_med({"date":S,"include_distance_km":B}),"small")
add("GoldenHourCalculator","Return the morning and evening golden-hour windows at a chosen location and date, useful for photography planning.",sch_med({"date":S,"latitude":N,"longitude":N}),"small")
add("VisiblePlanetsTonight","List which classical planets are visible to the naked eye from a chosen location tonight, with rise and set times and a recommended viewing window.",sch_med({"latitude":N,"longitude":N,"date":S,"min_altitude_degrees":N}),"medium")
add("MeteorShowerCalendar","Return upcoming meteor showers with peak dates, expected zenithal hourly rates, and a viewing-condition note based on the moon phase at peak.",sch_med({"start_date":S,"end_date":S,"min_zhr":I}),"medium")
add("ConstellationOverheadFinder","Return the constellations currently above a chosen horizon, with culmination times and the brightest star in each, suited to plan an evening's stargazing walk.",sch_large({"latitude":N,"longitude":N,"instant_iso":S,"min_altitude_degrees":N,"include_dim_constellations":B}),"medium")
add("SolarEclipseLookup","Return solar-eclipse events visible from a chosen region within a date window, with magnitude, totality duration, and local contact times.",sch_large({"latitude":N,"longitude":N,"start_date":S,"end_date":S,"include_partial":B}),"medium")

# ============================================================================
# DOMAIN 9: PLANT CARE / GARDENING
# ============================================================================
add("PlantWateringScheduler","Return a recommended watering cadence in days for a named houseplant species, adjusted for an indicated light level and pot size.",sch_med({"species":S,"light_level":E(["low","medium","bright_indirect","direct"]),"pot_diameter_cm":N}),"medium")
add("HardinessZoneLookup","Return the USDA or RHS hardiness zone for a named locality and the typical first and last frost dates.",sch_med({"locality":S,"standard":E(["usda","rhs"])}),"small")
add("CompanionPlantingAdvisor","Suggest companion and antagonist plants for a chosen vegetable, with a short rationale for each pairing such as pest deterrence or shade provision.",sch_med({"crop":S,"garden_style":E(["raised_bed","row","container","permaculture"])}),"medium")
add("SeedStartIndoorCalendar","Generate an indoor seed-starting calendar for a list of crops based on the last expected frost date at a chosen locality, including transplant-out windows.",sch_large({"crops":A(S),"locality":S,"last_frost_date":S,"use_grow_lights":B}),"large")
add("PestIdentificationTriage","Given a description of damage on a plant such as holes in leaves or yellow stippling, return the three most likely pests and a low-toxicity treatment option for each.",sch_large({"plant_species":S,"damage_description":S,"season":E(["spring","summer","fall","winter"]),"include_chemical_options":B}),"large")
add("HouseplantLightAuditor","Estimate whether a chosen indoor location provides adequate light for a named houseplant species, given window orientation and distance.",sch_med({"species":S,"window_orientation":E(["north","south","east","west","none"]),"distance_from_window_m":N}),"small")
add("PrunePlannerByMonth","Return a list of common ornamental shrubs that should be pruned in a chosen calendar month at a chosen climate zone.",sch_med({"month":E(["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]),"climate_zone":S}),"small")

# ============================================================================
# DOMAIN 10: SPORTS SCORE LOOKUP
# ============================================================================
add("LiveScoreboardReader","Return the current score, period, and clock for an ongoing match in a chosen league.",sch_med({"league":S,"match_id":S}),"small")
add("LeagueStandingsBoard","Return the current standings table for a chosen league and season including wins, losses, draws, points, and goal difference.",sch_med({"league":S,"season":S}),"medium")
add("HeadToHeadHistory","Return the historical head-to-head record between two teams across a chosen number of past meetings, with date, venue, and score.",sch_med({"team_a":S,"team_b":S,"past_meetings":I}),"small")
add("PlayerSeasonStatLine","Return a season stat line for a named player in a chosen league, with the per-game and totals view tailored to the sport.",sch_med({"player_name":S,"league":S,"season":S,"view":E(["per_game","totals"])}),"medium")
add("UpcomingFixtureCalendar","Return a chronological list of upcoming fixtures for a chosen team across a window of weeks, with home or away, kickoff time, and broadcaster.",sch_large({"team_name":S,"weeks_ahead":I,"include_cup_competitions":B,"tz_for_kickoffs":S}),"medium")
add("InjuryReportFeed","Return current injury statuses for a chosen team, with player name, body region, expected return window, and a confidence tag based on source reliability.",sch_large({"team_name":S,"league":S,"include_questionable":B,"include_long_term":B}),"medium")

# ============================================================================
# DOMAIN 11: KITCHEN / MEASUREMENT CONVERSION
# ============================================================================
add("BakeryWeightConverter","Convert a flour, sugar, or butter measurement between cups, grams, and ounces using ingredient-specific density factors.",sch_med({"ingredient":E(["all_purpose_flour","bread_flour","cake_flour","granulated_sugar","brown_sugar","butter","cocoa_powder"]),"value":N,"from_unit":S,"to_unit":S}),"medium")
add("OvenTemperatureCrossWalk","Translate a chosen oven temperature between Celsius, Fahrenheit, and gas-mark numbers.",sch_med({"value":N,"from_scale":E(["C","F","gas_mark"]),"to_scale":E(["C","F","gas_mark"])}),"small")
add("PanSizeSubstitutionGuide","Recommend a substitute baking pan when the called-for size is unavailable, returning a new pan plus any adjustment to baking time or temperature.",sch_large({"called_for_shape":E(["round","square","rectangular","loaf","springform","bundt"]),"called_for_size_cm":N,"available_shape":E(["round","square","rectangular","loaf","springform","bundt"]),"available_size_cm":N}),"medium")
add("YieldAdjuster","Adjust every quantity in a list of ingredient lines to a new final yield, preserving ratios and rounding sensibly for measuring tools.",sch_med({"ingredient_lines":A(S),"original_yield":N,"new_yield":N,"rounding_style":E(["fractional","decimal","metric"])}),"medium")

# ============================================================================
# DOMAIN 12: MOOD / JOURNAL HELPER
# ============================================================================
add("DailyMoodCheckIn","Record a one-line mood reading on a five-point valence and arousal grid for the current day.",sch_med({"valence":I,"arousal":I,"note":S}),"small")
add("JournalPromptGenerator","Return a single open-ended journaling prompt selected to nudge reflection on a chosen theme such as gratitude or boundaries.",sch_med({"theme":E(["gratitude","boundaries","work","relationships","creativity","grief","ambition","rest"]),"prompt_length":E(["short","medium","long"])}),"small")
add("MoodTrendChart","Return a chart of mood readings across the past chosen number of weeks, with weekly averages and any flagged trend changes that exceed a chosen threshold.",sch_large({"weeks_back":I,"threshold_change":N,"include_annotations":B,"include_arousal":B}),"medium")
add("EmotionVocabularyExpander","Return three more precise emotion words adjacent to a coarse seed emotion such as 'angry' or 'sad', drawn from a published emotion-wheel vocabulary.",sch_med({"seed_emotion":S,"specificity":E(["adjacent","one_step_out","two_steps_out"])}),"small")
add("JournalEntryWordCount","Return the word count, average sentence length, and most frequent content words for a draft journal entry, for a writer who wants gentle feedback on density.",sch_med({"entry_text":S,"min_word_length":I}),"small")
add("ReflectionPromptSeriesPlanner","Plan a week-long sequence of daily reflection prompts that build on each other along a chosen narrative arc such as 'closing out a project' or 'preparing for a move', returning one prompt per day with a brief framing note.",sch_large({"arc":E(["closing_a_project","preparing_for_a_move","grief_processing","new_year_intentions","relationship_repair","career_pivot"]),"start_date":S,"tone":E(["gentle","direct","challenging"]),"include_evening_check_in":B}),"large")

# ============================================================================
# DOMAIN 13: PET CARE REMINDER
# ============================================================================
add("PetFeedingReminder","Schedule a recurring feeding reminder for a named pet at a chosen daily time and portion size.",sch_med({"pet_name":S,"time_of_day":S,"portion_grams":N}),"small")
add("VetAppointmentTracker","Record an upcoming veterinary appointment for a named pet, including clinic name, date, and reason.",sch_med({"pet_name":S,"clinic_name":S,"appointment_date":S,"reason":S}),"medium")
add("VaccinationDueScheduler","Return the next due date for each routine vaccination for a named pet species and age, with a typical clinic interval.",sch_med({"species":E(["dog","cat","rabbit","ferret","bird"]),"age_months":I,"last_dose_dates":{"type":"object"}}),"medium")
add("DogWalkLogger","Log a completed dog walk with duration, distance, and a one-line note on the dog's behavior, mood, and any encounters with other animals.",sch_large({"pet_name":S,"duration_minutes":I,"distance_km":N,"behavior_note":S,"weather":E(["sunny","cloudy","rainy","snowy","hot","cold"])}),"medium")
add("LitterBoxCadenceTracker","Track when a multi-cat household's litter boxes were last scooped and emit a reminder when the cadence slips past a chosen threshold in hours.",sch_med({"household_id":S,"threshold_hours":I,"include_per_box_breakdown":B}),"medium")
add("PetWeightTracker","Record a weight reading for a named pet on the current date and return the trailing-month trend with a flag if the change exceeds a chosen percent.",sch_med({"pet_name":S,"weight_kg":N,"flag_threshold_percent":N}),"small")

# ============================================================================
# DOMAIN 14: WARDROBE / OUTFIT HELPER
# ============================================================================
add("OutfitWeatherMatcher","Suggest an outfit from a chosen wardrobe inventory that matches the day's forecast at a named locality, with separate top, bottom, and outerwear choices.",sch_large({"wardrobe_id":S,"locality":S,"date":S,"style_preference":E(["casual","business_casual","formal","athletic","streetwear"])}),"medium")
add("ColorCoordinationChecker","Check whether a candidate outfit's colors coordinate using a chosen harmony rule and flag any clashing pairs.",sch_med({"top_hex":S,"bottom_hex":S,"outerwear_hex":S,"harmony":E(["analogous","complementary","monochromatic","triadic"])}),"medium")
add("CapsuleWardrobePlanner","Plan a capsule wardrobe of a chosen target size across a chosen season, returning a recommended item list with quantity per category and a coverage check for typical weekly needs.",sch_large({"target_item_count":I,"season":E(["spring","summer","fall","winter","year_round"]),"lifestyle":E(["office","remote","creative","active","travel_heavy"]),"include_shoes":B,"include_outerwear":B}),"large")
add("FabricCareLookup","Return the recommended laundry, drying, and ironing settings for a fabric by name, with caveats for blends.",sch_med({"fabric_name":S,"is_blend":B}),"small")
add("ShoePairingForOccasion","Recommend shoes from a chosen wardrobe for a named occasion such as a wedding or a long flight.",sch_med({"wardrobe_id":S,"occasion":E(["wedding","interview","long_flight","gym","beach","dinner_party","commute"])}),"small")
add("WardrobeGapAnalyzer","Analyze a wardrobe inventory against a chosen lifestyle profile to identify the three to five items whose absence forces the most repeated outfits.",sch_large({"wardrobe_id":S,"lifestyle_profile":E(["office","remote","creative","active","travel_heavy","mixed"]),"include_accessories":B,"season_focus":E(["spring","summer","fall","winter","year_round"])}),"medium")

# ============================================================================
# DOMAIN 15: TRAVEL PLANNER
# ============================================================================
add("FlightFareWatcher","Watch a named city pair on chosen dates and alert when the round-trip fare drops below a target threshold.",sch_med({"origin":S,"destination":S,"depart_date":S,"return_date":S,"threshold_usd":N}),"medium")
add("ItineraryDayPlanner","Plan a single day in a named city with three to five activities chosen for a stated interest profile, with rough walking distances and meal-break slots.",sch_large({"city":S,"date":S,"interests":A(E(["museums","food","nature","architecture","nightlife","shopping","history"])),"pace":E(["relaxed","moderate","packed"]),"include_meal_breaks":B}),"large")
add("PackingListBuilder","Build a packing list for a chosen trip length, climate, and activity mix, with categories for clothing, toiletries, electronics, and documents.",sch_large({"days":I,"climate":E(["tropical","temperate","cold","desert","variable"]),"activities":A(S),"checked_bag":B,"include_documents_section":B}),"medium")
add("VisaRequirementLookup","Return the visa or entry-permit requirements for a passport-issuing country traveling to a destination country, with maximum stay and typical processing time.",sch_med({"passport_country":S,"destination_country":S,"purpose":E(["tourism","business","transit","study","work"])}),"medium")
add("LayoverActivitySuggester","Suggest activities for a layover of a chosen length at a named airport, with airside and landside options.",sch_med({"airport_iata":S,"layover_minutes":I,"have_visa":B}),"small")
add("HotelNeighborhoodBriefer","Return a brief on a named neighborhood in a destination city, with safety notes for evening, walkability score, and three landmark anchors.",sch_med({"city":S,"neighborhood":S,"traveler_profile":E(["solo","couple","family","business"])}),"medium")

# ============================================================================
# DOMAIN 16: SLEEP TRACKER
# ============================================================================
add("SleepSessionLogger","Log a completed sleep session with bedtime, wake time, and a one-line restfulness note.",sch_med({"bedtime_iso":S,"wake_iso":S,"restfulness_note":S}),"small")
add("SleepDebtCalculator","Calculate accumulated sleep debt against a chosen nightly target across the past seven days.",sch_med({"target_hours_per_night":N,"days_back":I}),"small")
add("ChronotypeQuiz","Administer a brief chronotype quiz and return a category from a published chronotype taxonomy such as morning lark or evening owl.",sch_med({"quiz_answers":A(S),"taxonomy":E(["meq","amo","custom"])}),"small")
add("NappingWindowAdvisor","Suggest the optimal afternoon nap window for a person based on their typical wake time and intended nap length, with caveats for evening sleep onset.",sch_med({"typical_wake_iso":S,"intended_nap_minutes":I,"evening_bedtime_iso":S}),"medium")
add("BedtimeRoutineBuilder","Build a personalized bedtime wind-down routine of three to seven steps based on a chosen target sleep time, current evening obligations, and stated stimulants such as caffeine or screens to wind down from.",sch_large({"target_sleep_iso":S,"evening_obligations":A(S),"stimulants_to_taper":A(E(["caffeine","alcohol","screens","intense_exercise","heavy_meals"])),"include_breathwork":B}),"large")
add("SleepEnvironmentAuditor","Audit a bedroom for sleep-friendliness across light, sound, temperature, and screen presence and return targeted improvements with rough cost.",sch_large({"bedroom_id":S,"include_cost_estimates":B,"currency":S,"season":E(["summer","winter","shoulder"])}),"medium")

# ============================================================================
# DOMAIN 17: SHOPPING LIST HELPER
# ============================================================================
add("ShoppingListAddItem","Add an item to the active shopping list with optional quantity and aisle hint.",sch_med({"item_name":S,"quantity":N,"aisle_hint":S}),"small")
add("ShoppingListCategorize","Reorder the active shopping list so items are grouped by store section such as produce, dairy, or pantry, given a chosen store layout.",sch_med({"list_id":S,"store_layout":E(["generic","trader_joes","whole_foods","costco","local_market"])}),"medium")
add("ShoppingListBudgetEstimator","Estimate the total cost of an active shopping list using recent typical prices at a chosen store and currency.",sch_med({"list_id":S,"store_name":S,"currency":S}),"medium")
add("WeeklyMealStaplesAutofill","Autofill the upcoming week's shopping list with household-defined staples such as milk, eggs, and bread, skipping items already on the list.",sch_med({"household_id":S,"week_starting":S,"skip_if_present":B}),"medium")
add("SubstituteWhenOutOfStock","Suggest a substitute item for a shopping-list entry that a chosen store reports as out of stock, ranked by closeness and price parity.",sch_med({"original_item":S,"store_name":S,"price_parity_weight":N}),"small")

# ============================================================================
# DOMAIN 18: HABIT TRACKER
# ============================================================================
add("HabitDailyCheckOff","Mark a habit as completed for the current day and update its running streak.",sch_med({"habit_id":S,"completed":B}),"small")
add("HabitStreakSummary","Return current and longest streaks for every active habit in a chosen tracker.",sch_med({"tracker_id":S,"include_inactive":B}),"small")
add("NewHabitDesigner","Help design a new habit using a stated trigger, behavior, and reward pattern, with a recommended starter cadence and a backslide recovery rule.",sch_large({"trigger_context":S,"intended_behavior":S,"reward_pattern":E(["intrinsic","external","social","none"]),"starter_cadence":E(["daily","alternate","three_per_week","weekly"]),"backslide_recovery_rule":S}),"large")
add("HabitChainVisualizer","Return a visual representation of habit completions across a chosen number of past days as a calendar grid with per-day status.",sch_med({"habit_id":S,"days_back":I,"color_by_streak_length":B}),"small")
add("HabitConflictDetector","Detect when two active habits typically schedule at overlapping times of day and suggest a deconfliction option.",sch_med({"tracker_id":S,"include_low_friction_conflicts":B}),"small")

# ============================================================================
# DOMAIN 19: ANNIVERSARY / BIRTHDAY REMINDER
# ============================================================================
add("BirthdayReminderRegister","Register a person's birthday for annual reminders, with optional relationship tag and preferred lead-time in days.",sch_med({"person_name":S,"month_day":S,"relationship":S,"lead_time_days":I}),"medium")
add("UpcomingOccasionsList","Return a chronological list of upcoming birthdays and anniversaries across a chosen window in days.",sch_med({"days_ahead":I,"include_anniversaries":B}),"small")
add("GiftIdeaBrainstormer","Brainstorm five gift ideas for a recipient given their stated interests, the occasion, and a budget range in a chosen currency.",sch_large({"recipient_interests":A(S),"occasion":E(["birthday","anniversary","holiday","graduation","housewarming","retirement"]),"budget_min":N,"budget_max":N,"currency":S}),"large")
add("CardMessageDrafter","Draft three card-message options for a chosen occasion and relationship, tunable along a warmth and humor axis.",sch_large({"occasion":E(["birthday","anniversary","sympathy","congratulations","thank_you"]),"relationship":S,"warmth":E(["low","medium","high"]),"humor":E(["none","gentle","heavy"]),"length":E(["short","medium","long"])}),"medium")
add("AnniversaryMilestoneNamer","Return the traditional and modern gift theme for a chosen wedding anniversary number such as 'paper' for the first year.",sch_small({"years":I}),"small")

# ============================================================================
# DOMAIN 20: RANDOM / DICE / COIN
# ============================================================================
add("CoinFlipper","Flip a fair virtual coin and return heads or tails.",sch_small({"include_edge_probability":B}),"small")
add("DiceRoller","Roll a chosen number of dice with a chosen number of sides each and return the per-die results and the sum.",sch_med({"count":I,"sides":I,"explode_on_max":B}),"small")
add("RandomIntegerPicker","Return a uniformly random integer between an inclusive lower and inclusive upper bound.",sch_med({"lower":I,"upper":I}),"small")
add("WeightedChoicePicker","Return one item drawn from a list of choices using per-item weights that need not sum to one.",sch_med({"choices":A(S),"weights":A(N)}),"small")
add("DungeonMastersDiceMacro","Roll a complex dice-macro expression in the standard tabletop notation and return per-die rolls, modifiers, and the final total, with support for advantage, disadvantage, and exploding dice.",sch_large({"expression":S,"advantage":B,"disadvantage":B,"explode_on_max":B,"label":S}),"large")
add("BingoCardGenerator","Generate a printable bingo card grid of a chosen size populated from a custom phrase pool.",sch_med({"size":I,"phrase_pool":A(S),"include_free_center":B}),"small")

# ============================================================================
# DOMAIN 21: JOKE / QUOTE GENERATOR
# ============================================================================
add("DailyJokeReader","Return one age-appropriate joke from a chosen category such as puns, dad jokes, or knock-knock.",sch_med({"category":E(["pun","dad_joke","knock_knock","one_liner","observational"]),"max_length":I}),"small")
add("InspirationalQuotePicker","Return one quotation matching a chosen theme, with attribution and the source work when known.",sch_med({"theme":E(["perseverance","creativity","leadership","stillness","change","craft","kindness"]),"max_length":I}),"small")
add("CustomQuoteFromAuthor","Return a quotation attributed to a named author across a chosen subject area, falling back to a 'no verified quotation' result rather than fabricating.",sch_large({"author_name":S,"subject":S,"min_length":I,"max_length":I,"fallback_to_adjacent_author":B}),"medium")
add("LimerickWriter","Compose a short five-line limerick on a chosen topic following the standard AABBA rhyme and meter pattern.",sch_med({"topic":S,"kid_friendly":B}),"small")
add("WordOfTheDayCard","Return a single word of the day with definition, etymology, and an example sentence, drawn from a chosen vocabulary band.",sch_med({"vocabulary_band":E(["common","intermediate","advanced","archaic","scientific"]),"include_etymology":B}),"small")
add("RoastBatchGenerator","Generate three gentle, affectionate roast lines for a friend based on a chosen quirk, with strict guardrails against punching down on protected categories or sensitive personal subjects.",sch_large({"friend_quirk":S,"tone":E(["gentle","playful","sharp"]),"max_length_per_line":I,"avoid_topics":A(S)}),"large")

# ============================================================================
# DOMAIN 22: QUIZ / TRIVIA
# ============================================================================
add("DailyTriviaQuestion","Return one trivia question on a chosen topic with the answer hidden behind a flag.",sch_med({"topic":S,"difficulty":E(["easy","medium","hard"]),"reveal_answer":B}),"small")
add("QuizDeckBuilder","Build a multiple-choice quiz deck of a chosen length on a chosen topic, with a chosen difficulty curve from warm-up to challenge.",sch_large({"topic":S,"deck_length":I,"difficulty_curve":E(["flat","ascending","mixed"]),"include_explanations":B,"answer_choice_count":I}),"large")
add("FlashcardSpacedRepetitionScheduler","Schedule the next review date for a flashcard based on the learner's most recent self-rating, using a standard spaced-repetition algorithm.",sch_med({"card_id":S,"rating":E(["again","hard","good","easy"]),"algorithm":E(["sm2","fsrs","leitner"])}),"medium")
add("TriviaCategoryPicker","Pick a balanced set of trivia categories for a chosen party size and average general-knowledge level.",sch_med({"party_size":I,"general_knowledge_level":E(["casual","balanced","competitive"]),"category_count":I}),"medium")
add("KnowledgeRetentionEstimator","Estimate the probability that a learner still remembers a flashcard given the time since last review and a chosen forgetting curve model.",sch_med({"card_id":S,"hours_since_last_review":N,"model":E(["ebbinghaus","fsrs","custom"])}),"small")
add("QuizScoreSummary","Summarize a finished quiz session with score, per-category accuracy, time spent per question, and a one-line takeaway phrased encouragingly.",sch_large({"session_id":S,"include_per_question_breakdown":B,"phrasing_style":E(["encouraging","neutral","brutally_honest"])}),"medium")

# ============================================================================
# DOMAIN MIX: extras to bring count over ~200 and fill any band gaps
# ============================================================================
add("EggBoilTimer","Start a kitchen timer tuned to a chosen egg doneness from soft to hard.",sch_small({"doneness":E(["soft","medium","hard"]),"egg_size":E(["small","medium","large","jumbo"])}),"small")
add("PomodoroSessionTimer","Start a focus-and-break timer cycle of a chosen work and break length.",sch_med({"work_minutes":I,"break_minutes":I,"cycles":I}),"small")
add("CountdownToDate","Return the days, hours, and minutes remaining until a target date.",sch_small({"target_date_iso":S}),"small")
add("BirthstoneLookup","Return the traditional and modern birthstone for a chosen birth month.",sch_small({"month":E(["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"])}),"small")
add("ChineseZodiacLookup","Return the Chinese zodiac animal and element for a chosen birth year.",sch_small({"year":I}),"small")
add("WesternZodiacLookup","Return the western zodiac sign for a chosen birth month and day.",sch_small({"month_day":S}),"small")
add("CoffeeBrewRatioAdvisor","Return a recommended coffee-to-water ratio in grams for a chosen brew method and target strength.",sch_med({"brew_method":E(["pour_over","french_press","aeropress","espresso","cold_brew","moka"]),"strength":E(["mild","standard","strong"])}),"small")
add("TeaBrewingTimer","Start a steep timer tuned to a chosen tea type and leaf grade.",sch_med({"tea_type":E(["green","black","oolong","white","puerh","herbal","matcha"]),"leaf_grade":E(["whole_leaf","broken","fannings"])}),"small")
add("WaterIntakeReminder","Schedule water-intake reminders across waking hours toward a chosen daily volume in milliliters.",sch_med({"daily_target_ml":I,"wake_iso":S,"sleep_iso":S}),"small")
add("StretchBreakSuggester","Suggest a short two-minute stretching routine targeted to a chosen body region.",sch_med({"body_region":E(["neck","shoulders","lower_back","hips","wrists","full_body"]),"include_breathing":B}),"small")
add("BreathworkPatternGuide","Guide a single breathwork session through a chosen pattern such as box breathing or four-seven-eight.",sch_med({"pattern":E(["box","four_seven_eight","resonant","alternate_nostril"]),"duration_minutes":I}),"small")
add("AlarmClockOnceScheduler","Schedule a one-time alarm at a chosen wall-clock instant in a chosen timezone.",sch_med({"target_iso":S,"zone":S,"label":S}),"small")
add("DayOfWeekResolver","Return the day of the week for a given calendar date.",sch_small({"date":S}),"small")

add("LeapYearChecker","Determine whether a chosen calendar year is a leap year under the Gregorian rules and return the cycle position.",sch_med({"year":I,"calendar":E(["gregorian","julian","revised_julian"])}),"medium")
add("AgeCalculatorByYears","Calculate the age in years, months, and days between a birth date and a reference date.",sch_med({"birth_date":S,"reference_date":S}),"medium")
add("FrostDateLookup","Return the average first and last frost dates and probability bands for a named locality.",sch_med({"locality":S,"probability_band":E(["10_percent","50_percent","90_percent"])}),"medium")
add("TideTableReader","Return high and low tide times and heights for a coastal locality on a chosen date.",sch_med({"locality":S,"date":S,"datum":E(["mllw","mlw","msl"])}),"medium")
add("PollenForecastReader","Report the day's pollen forecast across grass, tree, and weed categories for a named locality.",sch_med({"locality":S,"include_mold_spores":B}),"medium")
add("LocaleDateFormatter","Format an instant according to a chosen locale's conventional date and time presentation.",sch_med({"instant_iso":S,"locale":S,"style":E(["short","medium","long","full"])}),"medium")
add("CalorieBurnEstimator","Estimate calories burned during a chosen exercise type and intensity at a given body weight and duration.",sch_med({"activity":E(["walking","running","cycling","swimming","yoga","weightlifting","hiking"]),"intensity":E(["light","moderate","vigorous"]),"weight_kg":N,"duration_minutes":I}),"medium")
add("StepsToDistanceConverter","Convert a step count to an estimated distance using a chosen stride length or inferring from height.",sch_med({"steps":I,"stride_cm":N,"height_cm":N}),"medium")
add("BookReadingTimeEstimator","Estimate the reading time for a chosen book length in pages or words at a chosen reading speed.",sch_med({"pages":I,"words":I,"reading_speed_wpm":I}),"medium")
add("MoviePickerByMood","Pick three movies matching a chosen mood, runtime cap, and decade window.",sch_med({"mood":E(["uplifting","melancholic","thrilling","comforting","challenging"]),"max_runtime_minutes":I,"decade_window":A(I)}),"medium")
add("BookRecommendationByInterest","Recommend three books across a chosen interest area, length cap, and reading-difficulty band.",sch_med({"interest_area":S,"max_pages":I,"difficulty_band":E(["accessible","standard","dense"])}),"medium")
add("WordPuzzleAnagramFinder","Return anagrams of a chosen letter set, optionally filtered by minimum length and a chosen language vocabulary.",sch_med({"letters":S,"min_length":I,"language":S}),"medium")

add("TripCarbonFootprintEstimator","Estimate the carbon footprint of a planned trip across flight, train, car, and accommodation segments, with per-segment breakdown, comparison to a chosen baseline year, and a recommendation on the highest-leverage offset to consider.",sch_large({"segments":A({"type":"object","properties":{"mode":S,"distance_km":N,"nights":I}}),"baseline_year":I,"include_offset_recommendation":B,"currency":S}),"large")
add("WeeklyExerciseProgramBuilder","Build a one-week exercise program across a chosen number of training days, mixing aerobic, strength, mobility, and rest sessions, calibrated to a chosen fitness level and any equipment available at home.",sch_large({"training_days_per_week":I,"fitness_level":E(["beginner","intermediate","advanced"]),"home_equipment":A(S),"primary_goal":E(["general_fitness","strength","endurance","mobility","weight_loss"]),"max_session_minutes":I}),"large")
add("DinnerPartyMenuComposer","Compose a dinner party menu across appetizer, main, side, and dessert courses for a chosen guest count, dietary restrictions, target cuisine, and seasonal produce window, with a make-ahead timeline.",sch_large({"guest_count":I,"dietary_restrictions":A(S),"cuisine":S,"season":E(["spring","summer","fall","winter"]),"include_make_ahead_timeline":B,"wine_pairing":B}),"large")
add("RoadTripRouteBriefer","Brief a multi-stop road trip with overnight stops, scenic detours, and EV-charging notes if needed, given a chosen origin, destination, total days, and a preferred daily driving cap in hours.",sch_large({"origin":S,"destination":S,"total_days":I,"max_drive_hours_per_day":N,"vehicle_type":E(["ice","ev","hybrid"]),"scenic_preference":E(["minimal","moderate","heavy"])}),"large")
add("HomeMaintenanceSeasonalChecklist","Generate a seasonal home-maintenance checklist of ten to twenty tasks tuned to a chosen home type, climate, and ownership length, with rough time and cost estimates.",sch_large({"home_type":E(["apartment","condo","townhouse","detached_single_family","mobile"]),"climate":E(["tropical","temperate","cold","desert","coastal"]),"ownership_years":I,"include_cost_estimates":B,"currency":S}),"large")

# Additional small / medium fillers to balance the band distribution
add("HolidayCalendarChecker","Return whether a chosen calendar date is a public holiday in a chosen country and the holiday's local name.",sch_med({"date":S,"country":S}),"small")
add("RhymingWordSuggester","Return up to ten rhyming words for a chosen seed word, with perfect and near rhyme tiers.",sch_med({"seed_word":S,"tier":E(["perfect","near","both"])}),"small")
add("SynonymThesaurusLookup","Return synonyms for a chosen word with a chosen part-of-speech filter.",sch_med({"word":S,"part_of_speech":E(["noun","verb","adjective","adverb","any"])}),"small")
add("AntonymLookup","Return antonyms for a chosen word with a chosen part-of-speech filter.",sch_med({"word":S,"part_of_speech":E(["noun","verb","adjective","adverb","any"])}),"small")
add("FactOfTheDayCard","Return one curiosity fact on a chosen subject suitable for a glance card.",sch_med({"subject":S,"max_length":I}),"small")
add("HistoricalEventsOnThisDay","Return notable historical events that occurred on a given month and day across the past two centuries.",sch_med({"month_day":S,"category":E(["any","science","politics","arts","sports"])}),"medium")
add("CelebrityBirthdaysOnDate","Return public figures born on a given month and day across a chosen field.",sch_med({"month_day":S,"field":E(["any","film","music","sports","politics","science"])}),"small")
add("PlanetariumShowFinder","Find planetarium shows playing this week at venues within a chosen distance of a named city.",sch_med({"city":S,"max_distance_km":N,"week_starting":S}),"medium")
add("MuseumExhibitionFinder","Find current museum exhibitions on a chosen subject area within a named city.",sch_med({"city":S,"subject":S,"max_distance_km":N}),"medium")
add("FarmersMarketScheduleLookup","Return weekly farmers market schedules in a named city, with day, hours, and venue.",sch_med({"city":S,"day_of_week":E(["mon","tue","wed","thu","fri","sat","sun","any"])}),"small")
add("LocalEventsCalendar","Return upcoming local events of a chosen type within a chosen distance of a named city.",sch_med({"city":S,"event_type":E(["concert","festival","sports","fair","theater"]),"max_distance_km":N}),"medium")
add("PublicReadingRoomHoursLookup","Return the operating hours and current closures for a named public reading room.",sch_med({"room_name":S,"date":S}),"small")
add("RecyclingPickupCalendar","Return the next recycling pickup date for a chosen residential address, with sorting reminders.",sch_med({"address_line":S,"include_sort_reminders":B}),"small")
add("TrashPickupCalendar","Return the next general waste pickup date for a chosen residential address.",sch_med({"address_line":S,"include_holiday_shifts":B}),"small")
add("StreetParkingRules","Return the street parking rules at a chosen address, with cleaning days, meter hours, and permit zones.",sch_med({"address_line":S,"include_meter_rates":B}),"medium")
add("PublicTransitNextArrivals","Return the next three vehicle arrivals at a chosen stop on a named transit network.",sch_med({"stop_id":S,"network":S}),"small")
add("BikeShareStationStatus","Return the current bike and dock availability at a chosen bike-share station.",sch_med({"station_id":S,"network":S}),"small")
add("ElectricVehicleChargerFinder","Find compatible electric vehicle chargers within a chosen distance of a coordinate, with connector type and current availability.",sch_med({"latitude":N,"longitude":N,"connector_type":E(["ccs","chademo","tesla_nacs","j1772","type2"]),"max_distance_km":N}),"medium")
add("ParkingGarageAvailability","Return the current availability and posted hourly rate at a chosen parking garage.",sch_med({"garage_id":S,"include_max_daily":B}),"small")
add("WeatherClothingAdvisor","Recommend a clothing layer combination for a chosen forecast and activity level.",sch_med({"forecast_summary":S,"activity_level":E(["low","moderate","vigorous"])}),"small")
add("RainGearAdvisor","Recommend rain gear based on a chosen precipitation intensity and duration.",sch_med({"precip_intensity":E(["drizzle","light_rain","moderate_rain","heavy_rain","downpour"]),"duration_minutes":I}),"small")
add("UmbrellaForecastFlag","Return a binary umbrella-needed flag for the day at a named locality based on probability and duration thresholds.",sch_med({"locality":S,"probability_threshold":N,"duration_threshold_minutes":I}),"small")
add("PlantIdentifierByPhoto","Identify a plant species from an uploaded photo and return common name, scientific name, and care notes.",sch_med({"photo_id":S,"include_toxicity_note":B}),"small")
add("BirdSongIdentifier","Identify a likely bird species from an uploaded short audio clip and return common name and confidence.",sch_med({"audio_clip_id":S,"region_hint":S}),"small")
add("WildlifeSightingsLog","Log a wildlife sighting with species, location, time, and notes for personal nature-journaling.",sch_med({"species":S,"latitude":N,"longitude":N,"instant_iso":S,"notes":S}),"medium")
add("TidalPoolGuideByBeach","Return tidal pool exploration tips for a named beach, with safe windows around low tide and species commonly found.",sch_med({"beach_name":S,"date":S,"include_safety_warnings":B}),"medium")
add("HikingTrailDifficultyLookup","Return the rated difficulty, length, and elevation gain for a named hiking trail in a chosen park.",sch_med({"trail_name":S,"park_name":S}),"medium")
add("CampsiteAvailabilityLookup","Return the availability of named campsites within a chosen park on a target date range.",sch_med({"park_name":S,"start_date":S,"end_date":S,"site_type":E(["tent","rv","cabin","backcountry"])}),"medium")
add("DailySteptracker","Log the user's step count for the current day and update their trailing-week trend.",sch_med({"steps":I,"include_trend_chart":B}),"small")
add("HydrationLog","Log a hydration entry for the current day and return progress toward a chosen daily goal in milliliters.",sch_med({"volume_ml":I,"daily_goal_ml":I}),"small")
add("MeditationSessionLogger","Log a completed meditation session with duration, technique, and a one-line reflection.",sch_med({"duration_minutes":I,"technique":E(["mindfulness","loving_kindness","body_scan","mantra","breath_focus"]),"reflection":S}),"medium")
add("GratitudeListAdder","Add a one-line gratitude entry to the day's list.",sch_small({"entry":S}),"small")
add("WeeklyReviewPromptCard","Return a single weekly review prompt drawn from a chosen review framework such as wins-misses-next.",sch_med({"framework":E(["wins_misses_next","start_stop_continue","good_better_best","keep_drop_change"])}),"small")
add("BedtimeStoryReader","Read a short bedtime story tuned to a chosen age band and theme.",sch_med({"age_band":E(["toddler","preschool","early_elementary","late_elementary"]),"theme":E(["bravery","kindness","curiosity","friendship","adventure","calm"])}),"medium")
add("LullabyPlayer","Play a single instrumental lullaby tuned to a chosen tempo.",sch_med({"track_id":S,"tempo_bpm":I}),"small")
add("WhiteNoiseProfilePlayer","Play a chosen ambient noise profile such as rain, ocean, or fan at a chosen volume.",sch_med({"profile":E(["rain","ocean","fan","brown_noise","pink_noise","white_noise","forest"]),"volume_pct":I}),"small")
add("FocusPlaylistBuilder","Build a focus playlist of a chosen length tuned to a chosen energy level and any lyrical preference.",sch_med({"duration_minutes":I,"energy_level":E(["calm","moderate","energetic"]),"lyrical":E(["instrumental_only","sparse_lyrics","any"])}),"medium")
add("RecipeOfTheWeekFeed","Return a recipe of the week tuned to seasonal produce at a chosen locality.",sch_med({"locality":S,"week_starting":S,"meal_type":E(["breakfast","lunch","dinner","dessert","snack"])}),"medium")
add("KitchenInventoryTracker","Track the current pantry inventory with quantity, unit, and expiration date per item, with reminders for items approaching expiry.",sch_large({"household_id":S,"include_expiry_reminders":B,"days_before_expiry":I,"low_stock_threshold":N}),"medium")
add("LocalSeasonalProduceGuide","Return what produce is in peak season this month at a chosen locality.",sch_med({"locality":S,"month":S}),"small")
add("HerbalTeaBlendSuggester","Suggest a calming or energizing herbal blend based on a chosen mood goal.",sch_med({"mood_goal":E(["calm","focus","sleep","digestion","energy","immune_boost"]),"include_steeping_instructions":B}),"medium")
add("DailyAffirmationCard","Return one affirmation card on a chosen theme.",sch_med({"theme":E(["confidence","worthiness","calm","abundance","resilience"]),"max_length":I}),"small")
add("HoroscopeDailyCard","Return a one-paragraph daily horoscope for a chosen western zodiac sign.",sch_med({"sign":E(["aries","taurus","gemini","cancer","leo","virgo","libra","scorpio","sagittarius","capricorn","aquarius","pisces"]),"date":S}),"small")
add("FengShuiRoomAdvisor","Return high-level feng shui suggestions for a chosen room layout described by orientation and primary furniture placement.",sch_med({"room_orientation":E(["north","south","east","west"]),"primary_use":E(["sleep","work","social","kitchen","bath"]),"furniture_notes":S}),"medium")

# ============================================================================
# COMPACT SMALL-BAND ENTRIES (target token count 20-40)
# Single-property schemas + terse descriptions. These backfill the small band
# so the distribution lands roughly at the 1/3 - 1/3 - 1/3 target per
# PADDING_STRATEGY.md §3 corpus requirements.
# ============================================================================
_compact = {"type":"object","properties":{"x":{"type":"string"}}}
def smalle(name, desc, prop_name, prop_type):
    schema = {"type":"object","properties":{prop_name:prop_type},"required":[prop_name]}
    add(name, desc, schema, "small")

smalle("UnixTimestampNow","Return the current unix timestamp.","want_millis",B)
smalle("UnixToIsoConverter","Convert a unix timestamp to an ISO 8601 string.","ts",I)
smalle("IsoToUnixConverter","Convert an ISO 8601 string to a unix timestamp.","iso",S)
smalle("WeekNumberOfYear","Return the ISO week number for a date.","date",S)
smalle("DaysBetweenDates","Return the days between two dates.","date_a",S)
smalle("MonthsBetweenDates","Return the whole months between two dates.","date_a",S)
smalle("PrimeFactorizer","Factor an integer into primes.","n",I)
smalle("GreatestCommonDivisor","Compute the greatest common divisor.","a",I)
smalle("LeastCommonMultiple","Compute the least common multiple.","a",I)
smalle("FibonacciNumber","Return the nth Fibonacci number.","n",I)
smalle("RomanNumeralConverter","Convert an integer to its Roman numeral form.","n",I)
smalle("NumberToWordsConverter","Spell an integer out in English words.","n",I)
smalle("PercentageCalculator","Compute one number as a percentage of another.","part",N)
smalle("TipCalculator","Compute a tip amount.","bill",N)
smalle("BillSplitter","Split a bill across diners.","total",N)
smalle("PaceFromTime","Compute running pace per kilometer.","seconds",I)
smalle("BodyMassRatio","Compute body mass ratio from weight and height.","weight_kg",N)
smalle("ShoeSizeConverter","Convert a shoe size between regions.","size_us",N)
smalle("RingSizeConverter","Convert a ring size between regions.","size_us",N)
smalle("HatSizeConverter","Convert a hat size between regions.","size_us",N)
smalle("DressSizeConverter","Convert a dress size between regions.","size_us",N)
smalle("PantSizeConverter","Convert a pant size between regions.","waist_us",N)
smalle("BraSizeConverter","Convert a bra size between regions.","size_us",S)
smalle("PaperSizeLookup","Look up the dimensions of a paper size.","size_name",S)
smalle("EnvelopeSizeLookup","Look up the dimensions of an envelope size.","size_name",S)
smalle("CountryCallingNumber","Return the international calling prefix for a country.","country",S)
smalle("CurrencyOfCountry","Return the currency for a country.","country",S)
smalle("CapitalOfCountry","Return the capital of a country.","country",S)
smalle("LanguageOfCountry","Return the primary language of a country.","country",S)
smalle("FlagEmojiOfCountry","Return the flag emoji for a country.","country",S)
smalle("PhoneticAlphabetSpeller","Spell a word with the NATO phonetic alphabet.","word",S)
smalle("MorseEncoder","Encode a phrase in Morse signals.","text",S)
smalle("MorseDecoder","Decode a Morse signal string.","morse",S)
smalle("Base64Stringify","Encode a short string as base64.","text",S)
smalle("UpperCaseRender","Uppercase a string.","text",S)
smalle("TitleCaseRender","Title-case a string.","text",S)
smalle("SlugifyRender","Make a slug from a string.","text",S)
smalle("ReverseStringRender","Reverse a short string.","text",S)
smalle("PalindromeChecker","Check if a string is a palindrome.","text",S)
smalle("WordCountForText","Count words in a short passage.","text",S)
smalle("CharCountForText","Count characters in a short passage.","text",S)
smalle("RandomColorHex","Return a random valid hex color.","seed",I)
smalle("RandomCardDraw","Draw one card from a standard deck.","with_jokers",B)
smalle("RandomEmojiPicker","Return one random emoji from a category.","category",S)
smalle("RandomNameGenerator","Return one random name from a culture pool.","culture",S)
smalle("RandomPasswordPhrase","Return a random four-word passphrase.","wordlist",S)
smalle("LuckyNumberPicker","Return a lucky number for a person.","name",S)
smalle("DailyAffirmationShort","Return one short affirmation phrase.","theme",S)
smalle("MotivationalNudge","Return a short motivational nudge.","tone",S)
smalle("ComplimentGenerator","Return one short compliment.","category",S)
smalle("ApologyDrafterShort","Draft a short apology line.","situation",S)
smalle("ThankYouNoteShort","Draft a short thank-you note.","occasion",S)

# Build and validate
final = []
rejected = []
seen_names = set()

for idx, (name, desc, schema, band) in enumerate(ENTRIES):
    ok, reason = passes_qa(name, desc, schema)
    if not ok:
        rejected.append({"name": name, "reason": reason})
        continue
    if name in seen_names:
        rejected.append({"name": name, "reason": "duplicate_name"})
        continue
    seen_names.add(name)
    toks = tok_count(desc, schema)
    final.append({
        "name": name,
        "description": desc,
        "input_schema": schema,
        "estimated_tokens": toks,
        "_band": band,
    })

print(f"Total candidates: {len(ENTRIES)}", file=sys.stderr)
print(f"Accepted (pre-trim): {len(final)}", file=sys.stderr)
print(f"Rejected: {len(rejected)}", file=sys.stderr)
for r in rejected:
    print(f"  - {r}", file=sys.stderr)

# ----------------------------------------------------------------------------
# Trim corpus to TARGET_COUNT, preserving roughly 1/3-1/3-1/3 across bands.
# Bands are defined by tiktoken token count, NOT by author intent.
# Drop preferentially from the over-represented band; keep order-stable
# within bands so the SHA-256 stays deterministic.
# ----------------------------------------------------------------------------
TARGET_COUNT = 200

def measured_band(t):
    if t <= 40: return "small"
    if t <= 90: return "medium"
    return "large"

# annotate measured band on each entry
for e in final:
    e["_mband"] = measured_band(e["estimated_tokens"])

# Trim: drop from medium until we hit TARGET_COUNT
keep = []
medium_dropped = 0
target_per_band = TARGET_COUNT // 3 + 1  # ~67 each
band_counts = Counter(e["_mband"] for e in final)
# decide drop budget for medium: get medium down to roughly target_per_band
to_drop_medium = max(0, band_counts["medium"] - target_per_band)
remaining_drop = max(0, len(final) - TARGET_COUNT - to_drop_medium)

# Drop the last N medium entries (deterministic since ENTRIES is ordered)
medium_seen = 0
keep = []
for e in final:
    if e["_mband"] == "medium":
        medium_seen += 1
        if medium_seen > band_counts["medium"] - to_drop_medium:
            continue
    keep.append(e)

# If still over target, drop tail entries from any band (preserving balance roughly)
while len(keep) > TARGET_COUNT:
    # drop the next over-represented entry from the tail
    bc = Counter(e["_mband"] for e in keep)
    overrep = max(bc, key=bc.get)
    for i in range(len(keep)-1, -1, -1):
        if keep[i]["_mband"] == overrep:
            keep.pop(i)
            break

final = keep
print(f"Accepted (post-trim): {len(final)}", file=sys.stderr)

toks_only = [e["estimated_tokens"] for e in final]
bins = [(20,40,"small"),(41,90,"medium"),(91,180,"large")]
counts = {}
for lo, hi, lab in bins:
    counts[lab] = sum(1 for t in toks_only if lo <= t <= hi)
under = sum(1 for t in toks_only if t < 20)
over = sum(1 for t in toks_only if t > 180)
print(f"\nToken distribution:", file=sys.stderr)
print(f"  <20:     {under}", file=sys.stderr)
print(f"  20-40 (small):  {counts['small']}", file=sys.stderr)
print(f"  41-90 (medium): {counts['medium']}", file=sys.stderr)
print(f"  91-180 (large): {counts['large']}", file=sys.stderr)
print(f"  >180:    {over}", file=sys.stderr)
print(f"  min/max: {min(toks_only)}/{max(toks_only)}", file=sys.stderr)

OUT = str(Path(__file__).resolve().parents[2] / "design" / "fake_tool_corpus.jsonl")
with open(OUT, "w") as f:
    for e in final:
        e2 = {k:v for k,v in e.items() if not k.startswith("_")}
        f.write(json.dumps(e2, ensure_ascii=False) + "\n")
print(f"\nWrote {len(final)} entries to {OUT}", file=sys.stderr)

with open(OUT, "rb") as f:
    h = hashlib.sha256(f.read()).hexdigest()
print(f"SHA-256: {h}", file=sys.stderr)

stats = {
    "total_candidates": len(ENTRIES),
    "accepted": len(final),
    "rejected": rejected,
    "histogram": {
        "lt_20": under,
        "small_20_40": counts["small"],
        "medium_41_90": counts["medium"],
        "large_91_180": counts["large"],
        "gt_180": over,
    },
    "min_tokens": min(toks_only),
    "max_tokens": max(toks_only),
    "mean_tokens": sum(toks_only)/len(toks_only),
    "sha256": h,
    "seed": SEED,
    "band_target_counts_by_author": dict(Counter(e["_band"] for e in final)),
}
with open(str(Path(__file__).resolve().parent / "_fake_corpus_stats.json"),"w") as f:
    json.dump(stats, f, indent=2)
