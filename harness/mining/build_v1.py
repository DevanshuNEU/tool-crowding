"""Build the v1 public-tier rows for tasks/v1/queries.jsonl.

Run from harness/ root:
    python -m mining.build_v1                # online: computes fivegram audits via gh
    python -m mining.build_v1 --offline      # skip gh; emit empty audits (validates schema only)
    python -m mining.build_v1 --max-ngrams 8 --sleep 3

Output: writes ALL v1 public-tier rows to tasks/v1/queries.jsonl (overwrites).
The 5-gram audit column is populated for each query at write time so the launch
artifact ships with cached audits, not live-search artifacts.

Rows are grouped by source repo (per research/candidate_repos.md). The full
public tier requires 30 rows; sections are added one repo-batch per chat
session to preserve hand-curation quality.

Picks so far:
    pylint-dev/pylint     v1-pub-001 visit_call                 (PR #11033, 2026-05-22)
                          v1-pub-004 _set_state_on_block_lines  (PR #10868, 2026-02-26)
                          v1-pub-005 visit_functiondef          (PR #11037, 2026-05-23)
                          v1-pub-006 _worker_check_single_file  (PR #10997, 2026-05-07)
                          v1-pub-007 check_lines                (PR #10834, 2026-02-07)
    saulpw/visidata       v1-pub-002 adaptive_bufferer          (PR #3064,  2026-04-18)
    psycopg/psycopg       v1-pub-003 _maybe_prepare_gen         (PR #1260,  2026-02-18)
                          v1-pub-012 _should_discard             (PR #1307,  2026-05-21)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Path setup so the script is invokable as `python -m mining.build_pilot`
HARNESS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

from mining.audit_ngrams import compute_audit  # noqa: E402

# Each pilot query is laid out verbatim here so the artifact is auditable on
# inspection: every text, every line of ground truth, every metadata field is
# a literal in the source. The mining script then adds the fivegram_audit
# column before emitting JSONL.

PYLINT_VISIT_CALL_BODY = '''def visit_call(self, node: nodes.Call) -> None:
    # a len(S) call is used inside a test condition
    # could be if, while, assert or if expression statement
    # e.g. `if len(S):`
    if not utils.is_call_of_name(node, "len"):
        return
    # the len() call could also be nested together with other
    # boolean operations, e.g. `if z or len(x):`
    parent = node.parent
    while isinstance(parent, nodes.BoolOp):
        parent = parent.parent
    # we're finally out of any nested boolean operations so check if
    # this len() call is part of a test condition
    if not utils.is_test_condition(node, parent):
        return
    if not node.args:
        return
    len_arg = node.args[0]
    if isinstance(len_arg, (nodes.ListComp, nodes.SetComp, nodes.DictComp)):
        # The node is a comprehension as in len([x for x in ...])
        self.add_message(
            "use-implicit-booleaness-not-len",
            node=node,
            confidence=HIGH,
        )
        return
    try:
        instance = next(len_arg.infer())
    except astroid.InferenceError:
        # Probably undefined-variable, abort check
        return
    mother_classes = self.base_names_of_instance(instance)
    affected_by_pep8 = any(
        t in mother_classes for t in ("str", "tuple", "list", "set")
    )
    if "range" in mother_classes or (
        affected_by_pep8 and not self.instance_has_bool(instance)
    ):
        self.add_message(
            "use-implicit-booleaness-not-len",
            node=node,
            confidence=INFERENCE,
        )
'''

VISIDATA_ADAPTIVE_BUFFERER_BODY = '''def adaptive_bufferer(fp, max_buffer_size=65536):
    """Loading e.g. tsv files goes faster with a large buffer. But when the input stream
    is slow (e.g. 1 byte/second) and the buffer size is large, it can take a long time until
    the buffer is filled. Only when the buffer is filled (or the input stream is finished)
    you can see the data visualized in visidata. That's why we use an adaptive buffer.
    For fast input streams, the buffer becomes large, for slow input streams, the buffer stays
    small"""
    buffer_size = 8
    processed_buffer_size = 0
    t_read = 0
    t_fill_target = 1   #in seconds
    while True:
        t_preread = time.time()
        next_chunk = fp.read(buffer_size)
        t_postread = time.time()
        if not next_chunk:
            break
        yield next_chunk
        t_read += t_postread - t_preread
        processed_buffer_size += len(next_chunk)

        speed_ratio = t_read / t_fill_target
        if speed_ratio <= 0.5:
            # if filling the buffer takes less than half the ideal time, double the size of the buffer.
            buffer_size = min(buffer_size * 2, max_buffer_size)
        else:
            # adjust the buffer size proportionately to how long it took to fill
            buffer_size = math.ceil(min(processed_buffer_size / speed_ratio, max_buffer_size))
            processed_buffer_size = 0
            t_read = 0
'''

VISIDATA_PLOT_SEABORN_BODY = '''def plot_seaborn(vd, rows, xcols, ycols):
    vd.status(f'plotting {len(rows)} rows using matplotlib')
    # import all libraries used by ext_plot_seaborn() inside the originating visidata process,
    # not the spawned process, so they stay imported for speed on subsequent calls
    global pyplot, seaborn
    pyplot = vd.importExternal('matplotlib.pyplot', 'matplotlib')
    seaborn = vd.importExternal('seaborn')
    import multiprocessing
    mp = multiprocessing.Process(target=ext_plot_seaborn, args=(vd, rows, xcols, ycols))
    mp.start()
'''

VISIDATA_FREQTBL_SELECTROW_BODY = '''def selectRow(self, row):
    # Does not create an undo-operation for the select on the source rows. The caller should create undo-information itself.
    for r in Progress(row.sourcerows, 'selecting'):
        self.source.selectRow(r)
    return super().selectRow(row)  # then select the bin itself on this sheet
'''

VISIDATA_ITERDISPVALS_BODY = '''def iterdispvals(sheet, *cols, format=False, delimiter=None):
    \'For each row in sheet, yield OrderedDict of values for given cols.  Values are typed if format=False, or a formatted display string if format=True.\'
    if not cols:
        cols = sheet.visibleCols

    transformers = collections.OrderedDict()  # list of transformers for each column in order
    trdict = sheet.safe_trdict(delimiter=delimiter)
    for col in cols:
        transformers[col] = [ col.type ]
        if format:
            formatMaker = getattr(col, 'formatter_'+(col.formatter or sheet.options.disp_formatter))
            transformers[col].append(formatMaker(col._formatdict))
        if trdict:
            transformers[col].append(lambda v,trdict=trdict: v.translate(trdict))

    options_safe_error = sheet.options.safe_error
    for r in sheet.iterrows('saving'):
        dispvals = collections.OrderedDict()  # [col] -> value
        for col, transforms in transformers.items():
            try:
                dispval = col.getValue(r)

            except Exception as e:
                dispval = options_safe_error or str(e)

            try:
                for t in transforms:
                    if dispval is None or isinstance(dispval, float) and dispval != dispval:
                        break
                    elif isinstance(dispval, TypedExceptionWrapper):
                        dispval = options_safe_error or str(dispval)
                        break
                    elif isinstance(dispval, TypedWrapper):
                        dispval = ''
                        break
                    else:
                        dispval = t(dispval)

                if (dispval is None or isinstance(dispval, float) and dispval != dispval) and format:
                    dispval = ''
            except Exception as e:
                dispval = str(dispval)

            dispvals[col] = dispval

        yield dispvals
'''

VISIDATA_ADDCOL_EXPR_BODY = '''def addcol_expr(sheet, expr_input, **kwargs):  # #3022
    \'Parse "name=expr" and return an ExprColumn. If no name given, use the expression as the name.\'
    name, expr = expr_input, None
    eq_idx = expr_input.find('=')
    if eq_idx > 0:
        lhs = expr_input[:eq_idx].strip()
        rhs = expr_input[eq_idx+1:]
        if lhs.isidentifier() and rhs and rhs[0] != '=':
            expr = rhs.strip() or None
            if expr:
                name = lhs
    return ExprColumn(name, expr=expr, **kwargs)
'''

BUILDBOT_SETUP_SUPPRESSION_BODY = '''def setup_suppression(self) -> InlineCallbacksType[None]:
    if self.suppressionList is not None:
        self.addSuppression(self.suppressionList)  # type: ignore[arg-type]

    if self.suppressionFile is not None:
        # Create a temporary file to avoid reading everything into memory at once.
        fd, tmpname = tempfile.mkstemp(prefix='buildbot-suppressions-')
        os.close(fd)
        try:
            # Use uploadFile directly with FileWriter to download to a temp file.
            # This avoids loading the entire file into the master's memory.
            upload_args = {
                'workdir': self.workdir,
                'writer': remotetransfer.FileWriter(tmpname, maxsize=None, mode=None),
                'maxsize': None,
                'blocksize': 32 * 1024,
            }
            if self.workerVersionIsOlderThan('uploadFile', '3.0'):
                upload_args['slavesrc'] = self.suppressionFile
            else:
                upload_args['workersrc'] = self.suppressionFile

            yield self.runRemoteCommand(
                'uploadFile',
                upload_args,
                abandonOnFailure=True,
            )

            # Parse the file in a background thread to prevent blocking the master's main event
            # loop.
            suppressions = yield threads.deferToThread(self._parse_suppression_file, tmpname)
            self.addSuppression(suppressions)
        finally:
            if os.path.exists(tmpname):
                os.unlink(tmpname)
'''

BUILDBOT_GET_ANY_ACCESS_BODY = '''async def _get_any_access_allowed(user_info: dict[str, Any], authz: Authz) -> bool:
    try:
        await any_to_async(auth.assert_user_allowed_any_access(authz, user_info))
        return True
    except Exception:
        return False
'''

BUILDBOT_TRIGGER_RUN_BODY = '''def run(self) -> InlineCallbacksType[int]:
    schedulers_and_props = yield self.getSchedulersAndProperties()

    schedulers_and_props_list: list[dict[str, Any]] = []

    # To be back compatible we need to differ between old and new style
    # schedulers_and_props can either consist of 2 elements tuple or
    # dictionary
    for element in schedulers_and_props:
        if isinstance(element, dict):
            schedulers_and_props_list = schedulers_and_props
            break
        # Old-style back compatibility: Convert tuple to dict and make
        # it important
        d = {'sched_name': element[0], 'props_to_set': element[1], 'unimportant': False}
        schedulers_and_props_list.append(d)

    # post process the schedulernames, and raw properties
    # we do this out of the loop, as this can result in errors
    schedulers_and_props = [
        (
            self.getSchedulerByName(entry_dict['sched_name']),
            self.createTriggerProperties(entry_dict['props_to_set']),
            entry_dict['unimportant'],
        )
        for entry_dict in schedulers_and_props_list
    ]

    ss_for_trigger = self.prepareSourcestampListForTrigger()

    dl: list[defer.Deferred[Any]] = []
    triggeredNames: list[str] = []
    results = SUCCESS
    self.running = True

    unimportant_brids: list[int] = []

    # Transmit the maximum priority of the buildrequest of this build to the
    # triggered buildrequests
    priority = max(r.priority for r in self.build.requests)  # type: ignore[union-attr]

    for sch, props_to_set, unimportant in schedulers_and_props:
        idsDeferred, resultsDeferred = sch.trigger(
            waited_for=self.waitForFinish,
            sourcestamps=ss_for_trigger,
            set_props=props_to_set,
            parent_buildid=self.build.buildid,  # type: ignore[union-attr]
            parent_relationship=self.parent_relationship,
            priority=priority,
        )
        # we are not in a hurry of starting all in parallel and managing
        # the deferred lists, just let the db writes be serial.
        brids: dict[Any, Any] = {}
        try:
            _, brids = yield idsDeferred
        except Exception as e:
            yield self.addLogWithException(e)
            results = EXCEPTION
        if unimportant:
            unimportant_brids.extend(brids.values())
        self.brids.extend(brids.values())
        for brid in brids.values():
            # put the url to the brids, so that we can have the status from
            # the beginning
            url = getURLForBuildrequest(self.master, brid)  # type: ignore[arg-type]
            yield self.addURL(f"{sch.name} #{brid}", url)
            # No yield since we let this happen as the builds complete
            self._add_results(brid)

        dl.append(resultsDeferred)
        triggeredNames.append(sch.name)
        if self.ended:
            return CANCELLED
    self.triggeredNames = triggeredNames

    if self.waitForFinish:
        self.waitForFinishDeferred = defer.DeferredList(dl, consumeErrors=True)
        try:
            rclist = yield self.waitForFinishDeferred
        except defer.CancelledError:
            pass
        # we were interrupted, don't bother update status
        if self.ended:
            return CANCELLED
        yield self.addBuildUrls(rclist)
        results = yield self.worstStatus(results, rclist, unimportant_brids)
    else:
        # do something to handle errors
        for deferred in dl:
            deferred.addErrback(log.err, '(ignored) while invoking Triggerable schedulers:')

    return results
'''

BUILDBOT_ONJOIN_BODY = '''def onJoin(self, details: SessionDetails) -> InlineCallbacksType[None]:
    self._logger.info("Wamp connection succeed (authid={authid})!", authid=self.authid)
    for handler in [self, *self.services]:
        yield self.register(handler)
        yield self.subscribe(handler)
    yield self.publish(f"org.buildbot.{self.master.masterid}.connected")
    self.parent.service = self  # type: ignore[attr-defined]
    self.parent.serviceDeferred.callback(self)  # type: ignore[attr-defined]
'''


PSYCOPG_SHOULD_DISCARD_BODY = '''def _should_discard(
    self,
    prep: Prepare,
    results: Sequence[PGresult],
    __should_clear: Any = re.compile(rb"^(?:DROP|ALTER|ROLLBACK|DISCARD)\\b").match,
) -> bool:
    """Check if we need to discard our entire state: it should happen on
    rollback or on dropping objects, because the same object may get
    recreated and postgres would fail internal lookups.
    """
    if self._names or prep == Prepare.SHOULD:
        for result in results:
            if result.status != COMMAND_OK:
                continue
            if (cmdstat := result.command_status) and __should_clear(cmdstat):
                return self.clear()
    return False
'''

PSYCOPG_MAYBE_PREPARE_GEN_BODY = '''def _maybe_prepare_gen(
    self,
    pgq: PostgresQuery,
    *,
    prepare: bool | None = None,
    binary: bool | None = None,
) -> PQGen[None]:
    # Check if the query is prepared or needs preparing
    prep, name = self._get_prepared(pgq, prepare)
    if prep is Prepare.NO:
        # The query must be executed without preparing
        self._execute_send(pgq, binary=binary)
    else:
        # If the query is not already prepared, prepare it.
        if prep is Prepare.SHOULD:
            self._send_prepare(name, pgq)
            if not self._conn._pipeline:
                results = yield from execute(self._pgconn)
                for result in results:
                    if result.status == FATAL_ERROR:
                        raise e.error_from_result(result, encoding=self._encoding)
        # Then execute it.
        self._send_query_prepared(name, pgq, binary=binary)

    # Update the prepare state of the query.
    # If an operation requires to flush our prepared statements cache,
    # it will be added to the maintenance commands to execute later.
    key = self._conn._prepared.maybe_add_to_cache(pgq, prep, name)

    if self._conn._pipeline:
        queued = None
        if key is not None:
            queued = (key, prep, name)
        self._conn._pipeline.result_queue.append((self, queued))
        return

    # run the query
    results = yield from execute(self._pgconn)

    if key is not None:
        self._conn._prepared.validate(key, prep, name, results)

    self._check_results(results)
    self._set_results(results)
'''


PYLINT_FILE_STATE_BODY = '''def _set_state_on_block_lines(
    self,
    msgs_store: MessageDefinitionStore,
    node: nodes.NodeNG,
    msg: MessageDefinition,
    msg_state: dict[int, bool],
) -> None:
    """Recursively walk (depth first) AST to collect block level options
    line numbers and set the state correctly.
    """
    # Avoid recursing into child nodes on the same line.
    if node.lineno != node.end_lineno:
        for child in node.get_children():
            self._set_state_on_block_lines(msgs_store, child, msg, msg_state)
    # first child line number used to distinguish between disable
    # which are the first child of scoped node with those defined later.
    # For instance in the code below:
    #
    # 1.   def meth8(self):
    # 2.        """test late disabling"""
    # 3.        pylint: disable=not-callable, useless-suppression
    # 4.        print(self.blip)
    # 5.        pylint: disable=no-member, useless-suppression
    # 6.        print(self.bla)
    #
    # E1102 should be disabled from line 1 to 6 while E1101 from line 5 to 6
    #
    # this is necessary to disable locally messages applying to class /
    # function using their fromlineno
    if (
        isinstance(node, (nodes.Module, nodes.ClassDef, nodes.FunctionDef))
        and node.body
    ):
        firstchildlineno = node.body[0].fromlineno
    else:
        firstchildlineno = node.tolineno
    self._set_message_state_in_block(msg, msg_state, node, firstchildlineno)
'''

PYLINT_VISIT_FUNCTIONDEF_BODY = '''def visit_functiondef(self, node: nodes.FunctionDef) -> None:
    """Check method arguments, overriding."""
    # ignore actual functions
    if not node.is_method():
        return

    self._check_useless_super_delegation(node)
    self._check_property_with_parameters(node)

    # 'is_method()' is called and makes sure that this is a 'nodes.ClassDef'
    klass: nodes.ClassDef = node.parent.frame()
    # check first argument is self if this is actually a method
    self._check_first_arg_for_type(node, klass.type == "metaclass")
    if node.name == "__init__":
        self._check_init(node, klass)
        return
    # check signature if the method overloads inherited method
    for overridden in klass.local_attr_ancestors(node.name):
        # get astroid for the searched method
        try:
            parent_function = overridden[node.name]
        except KeyError:
            # we have found the method but it's not in the local
            # dictionary.
            # This may happen with astroid build from living objects
            continue
        if not isinstance(parent_function, nodes.FunctionDef):
            continue
        self._check_signature(node, parent_function, klass)
        self._check_invalid_overridden_method(node, parent_function)
        break

    if node.decorators:
        for decorator in node.decorators.nodes:
            match decorator:
                case nodes.Attribute(attrname="getter" | "setter" | "deleter"):
                    # attribute affectation will call this method, not hiding it
                    return
                case nodes.Name(name="property"):
                    return
                case nodes.Attribute():
                    if self._check_functools_or_not(decorator):
                        return

            # Infer the decorator and see if it returns something useful
            inferred = safe_infer(decorator)
            if not inferred:
                return
            if (
                isinstance(inferred, nodes.ClassDef)
                and inferred.qname() == "functools.cached_property"
            ):
                return
            if isinstance(inferred, nodes.FunctionDef):
                # Okay, it's a decorator, let's see what it can infer.
                try:
                    inferred = next(inferred.infer_call_result(inferred))
                except astroid.InferenceError:
                    return
            try:
                if (
                    isinstance(inferred, (astroid.Instance, nodes.ClassDef))
                    and inferred.getattr("__get__")
                    and inferred.getattr("__set__")
                ):
                    return
            except astroid.AttributeInferenceError:
                pass

    # check if the method is hidden by an attribute
    # pylint: disable = too-many-try-statements
    try:
        overridden = klass.instance_attr(node.name)[0]
        overridden_frame = overridden.frame()
        match overridden_frame:
            case nodes.FunctionDef(type="method"):
                overridden_frame = overridden_frame.parent.frame()
        if not (
            isinstance(overridden_frame, nodes.ClassDef)
            and klass.is_subtype_of(overridden_frame.qname())
        ):
            return

        # If a subclass defined the method then it's not our fault.
        for ancestor in klass.ancestors():
            if node.name in ancestor.instance_attrs and is_attr_private(node.name):
                return
            for obj in ancestor.lookup(node.name)[1]:
                if isinstance(obj, nodes.FunctionDef):
                    return
        args = (overridden.root().name, overridden.fromlineno)
        self.add_message("method-hidden", args=args, node=node)
    except astroid.NotFoundError:
        pass
'''

PYLINT_WORKER_CHECK_BODY = '''def _worker_check_single_file(
    file_item: FileItem,
) -> tuple[
    int,
    str,
    str,
    str,
    list[Message],
    LinterStats,
    int,
    defaultdict[str, list[Any]],
]:
    import multiprocessing  # pylint: disable=import-outside-toplevel

    if not _worker_linter:
        raise RuntimeError("Worker linter not yet initialised")

    # A worker process can lint multiple files. The parent process expects the
    # returned LinterStats instance to describe only the current file because it
    # merges one stats object per _worker_check_single_file() result. If we keep
    # the worker-level accumulated stats here, values such as stats.by_msg are
    # counted repeatedly in the final report.
    _worker_linter.stats = LinterStats()
    _worker_linter.msg_status = 0

    _worker_linter.open()
    _worker_linter.check_single_file_item(file_item)
    mapreduce_data = defaultdict(list)
    for checker in _worker_linter.get_checkers():
        data = checker.get_map_data()
        if data is not None:
            mapreduce_data[checker.name].append(data)
    msgs = _worker_linter.reporter.messages
    assert isinstance(_worker_linter.reporter, reporters.CollectingReporter)
    _worker_linter.reporter.reset()
    return (
        id(multiprocessing.current_process()),
        _worker_linter.current_name,
        file_item.filepath,
        _worker_linter.file_state.base_name,
        msgs,
        _worker_linter.stats,
        _worker_linter.msg_status,
        mapreduce_data,
    )
'''

PYLINT_CHECK_LINES_BODY = '''def check_lines(
    self, tokens: TokenWrapper, line_start: int, lines: str, lineno: int
) -> None:
    """Check given lines for potential messages.

    Check if lines have:
    - a final newline
    - no trailing white-space
    - less than a maximum number of characters
    """
    # we're first going to do a rough check whether any lines in this set
    # go over the line limit. If none of them do, then we don't need to
    # parse out the pylint options later on and can just assume that these
    # lines are clean

    # we'll also handle the line ending check here to avoid double-iteration
    # unless the line lengths are suspect

    max_chars = self.linter.config.max_line_length

    split_lines = self.specific_splitlines(lines)

    for offset, line in enumerate(split_lines):
        if not line.endswith("\\n"):
            self.add_message("missing-final-newline", line=lineno + offset)
            continue
        # We don't test for trailing whitespaces in strings
        # See https://github.com/pylint-dev/pylint/issues/6936
        # and https://github.com/pylint-dev/pylint/issues/3822
        if tokens.type(line_start) != tokenize.STRING:
            self.check_trailing_whitespace_ending(line, lineno + offset)

    # This check is purposefully simple and doesn't rstrip since this is running
    # on every line you're checking it's advantageous to avoid doing a lot of work
    potential_line_length_warning = any(
        len(line) > max_chars for line in split_lines
    )

    # if there were no lines passing the max_chars config, we don't bother
    # running the full line check (as we've met an even more strict condition)
    if not potential_line_length_warning:
        return

    # Line length check may be deactivated through `pylint: disable` comment
    mobj = OPTION_PO.search(lines)
    checker_off = False
    if mobj:
        if not self.is_line_length_check_activated(mobj):
            checker_off = True
        # The 'pylint: disable whatever' should not be taken into account for line length count
        lines = self.remove_pylint_option_from_lines(mobj)

    ignore_pattern_in_long_lines = self.linter.config.ignore_pattern_in_long_lines
    if ignore_pattern_in_long_lines:
        lines = ignore_pattern_in_long_lines.sub("", lines)

    # here we re-run specific_splitlines since we have filtered out pylint options above
    for offset, line in enumerate(self.specific_splitlines(lines)):
        self.check_line_length(line, lineno + offset, checker_off)
'''


# archinstall uses tab indentation throughout its source tree; the bodies below
# preserve that. The 5-gram audit normalizes whitespace to single spaces before
# the GitHub Code Search query (see mining/audit_ngrams.py:_extract_5grams), so
# tab-vs-space choice does not affect audit fidelity.

ARCHINSTALL_USER_SET_SHELL_BODY = '''def user_set_shell(self, user: str, shell: str) -> bool:
	info(f'Setting shell for {user} to {shell}')

	cmd = ['arch-chroot', '-S', str(self.target), 'chsh', '-s', shell, user]
	try:
		run(cmd)
		return True
	except CalledProcessError as err:
		debug(f'Error setting user shell: {err}')
		return False
'''

ARCHINSTALL_IS_NVIDIA_PROPRIETARY_BODY = '''def is_nvidia_proprietary(self) -> bool:
	"""
	True for Nvidia drivers that ship proprietary userspace components.
	Currently only NvidiaOpenKernel (nvidia-open-dkms): open kernel module
	paired with proprietary userspace. NvidiaOpenSource (nouveau) is fully
	open and works with Sway, so it is excluded.
	"""
	match self:
		case GfxDriver.NvidiaOpenKernel:
			return True
		case _:
			return False
'''

ARCHINSTALL_AS_SUMMARY_BODY = '''def as_summary(self) -> str:
	"""
	Render a concise two-column summary of the current configuration.

	The left column holds section labels, the right column holds values.
	Column width adapts to the longest translated label so translations
	do not break the alignment. Rows whose underlying config is not set
	are skipped.

	Returns an empty string if nothing meaningful to show.
	"""
	rows: list[tuple[str, str]] = []

	disk_config = self._config.disk_config
	if disk_config and disk_config.device_modifications:
		disk_parts: list[str] = []
		for mod in disk_config.device_modifications:
			path = str(mod.device_path)
			root_part = mod.get_root_partition()
			flags: list[str] = []
			if root_part and root_part.fs_type:
				flags.append(root_part.fs_type.value)
			if disk_config.disk_encryption:
				flags.append(tr('LUKS'))
			disk_parts.append(f'{path} ({" + ".join(flags)})' if flags else path)
		rows.append((tr('Disks'), ', '.join(disk_parts)))

	bl_config = self._config.bootloader_config
	if bl_config and bl_config.bootloader != Bootloader.NO_BOOTLOADER:
		rows.append((tr('Bootloader'), bl_config.bootloader.value))

	kernels = self._config.kernels
	if kernels:
		rows.append((tr('Kernel'), ', '.join(kernels)))

	profile_config = self._config.profile_config
	if profile_config and profile_config.profile:
		names = profile_config.profile.current_selection_names()
		rows.append((tr('Profile'), ', '.join(names) if names else profile_config.profile.name))
		if profile_config.greeter:
			rows.append((tr('Greeter'), profile_config.greeter.value))

	packages = self._config.packages
	if packages:
		rows.append((tr('Packages'), str(len(packages))))

	net_config = self._config.network_config
	if isinstance(net_config, NetworkConfiguration):
		rows.append((tr('Network'), net_config.type.display_msg()))

	locale_config = self._config.locale_config
	if locale_config:
		rows.append((tr('Locale'), locale_config.sys_lang))

	tz = self._config.timezone
	if tz:
		rows.append((tr('Timezone'), tz))

	if not rows:
		return ''

	label_width = max(len(label) for label, _ in rows) + 2
	return '\\n'.join(f'{label:<{label_width}}{value}' for label, value in rows)
'''

ARCHINSTALL_BSPWM_PROVISION_BODY = '''def provision(self, install_session: Installer, users: list[User]) -> None:
	for user in users:
		install_session.arch_chroot('mkdir -p ~/.config/bspwm ~/.config/sxhkd', run_as=user.username)
		install_session.arch_chroot('cp /usr/share/doc/bspwm/examples/bspwmrc ~/.config/bspwm/', run_as=user.username)
		install_session.arch_chroot('cp /usr/share/doc/bspwm/examples/sxhkdrc ~/.config/sxhkd/', run_as=user.username)
		install_session.arch_chroot('chmod +x ~/.config/bspwm/bspwmrc', run_as=user.username)
'''

ARCHINSTALL_SELECT_CONSOLE_FONT_BODY = '''async def select_console_font(preset: str | None = None) -> str | None:
	fonts = list_console_fonts()

	items = [MenuItem(f, value=f) for f in fonts]
	group = MenuItemGroup(items, sort_items=False)
	group.set_focus_by_value(preset)

	result = await Selection[str](
		header=tr('Console font'),
		group=group,
		enable_filter=True,
	).show()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled return type')
'''


PILOT_ROWS: list[dict] = [
    # ============================================================
    # pylint-dev/pylint  (GPL-2.0)
    # ============================================================
    {
        "query_id": "v1-pub-001",
        "tier": "public",
        "text": (
            "In pylint, find the refactoring-checker visitor method that fires the "
            "`use-implicit-booleaness-not-len` warning when `len()` is used inside a "
            "boolean test condition such as `if len(my_list):`. The method visits "
            "Call nodes, walks past any enclosing boolean operations, and must avoid "
            "crashing when `len()` is invoked with no arguments at all (e.g. `if len():`)."
        ),
        "ground_truth_target": "visit_call",
        "ground_truth_code": PYLINT_VISIT_CALL_BODY,
        "source_repo": "pylint-dev/pylint",
        "source_publication_date": "2026-05-22",
        "source_license": "GPL-2.0",
        "difficulty_quartile": "q3",  # 47-line body
        "primary_server": "oci",
        # fivegram_audit is filled in by the mining loop below.
    },
    {
        "query_id": "v1-pub-004",
        "tier": "public",
        "text": (
            "In pylint, find the file-state utility method that walks an AST "
            "depth-first to compute the per-line on/off state for a single message "
            "based on inline `# pylint: disable=...` directives. The method is "
            "recursive over the node's children, distinguishes between a disable "
            "directive that is the first statement inside a scope (module, class, "
            "or function body) versus one defined later in the scope, and was "
            "recently optimized to skip descending into children whenever the "
            "current node starts and ends on the same line."
        ),
        "ground_truth_target": "_set_state_on_block_lines",
        "ground_truth_code": PYLINT_FILE_STATE_BODY,
        "source_repo": "pylint-dev/pylint",
        "source_publication_date": "2026-02-26",
        "source_license": "GPL-2.0",
        "difficulty_quartile": "q2",  # 37-line body
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-005",
        "tier": "public",
        "text": (
            "In pylint, find the class-checker visitor method that runs on every "
            "FunctionDef whose parent is a class. The method dispatches several "
            "method-level checks (useless super-delegation, property-with-parameters, "
            "signature compatibility against any overridden ancestor) and then "
            "decides whether to emit the `method-hidden` warning. As part of that "
            "decision it walks the function's decorators and returns early for "
            "`@property`, `@cached_property`, attribute getters/setters/deleters, "
            "and any descriptor whose inferred type defines both `__get__` and "
            "`__set__`."
        ),
        "ground_truth_target": "visit_functiondef",
        "ground_truth_code": PYLINT_VISIT_FUNCTIONDEF_BODY,
        "source_repo": "pylint-dev/pylint",
        "source_publication_date": "2026-05-23",
        "source_license": "GPL-2.0",
        "difficulty_quartile": "q4",  # 94-line body
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-006",
        "tier": "public",
        "text": (
            "In pylint, find the worker entrypoint that runs inside each subprocess "
            "when pylint is invoked with `--jobs` greater than 1. The function "
            "checks one file at a time and returns the per-file results back to the "
            "parent process for merging. It resets the worker linter's `stats` and "
            "`msg_status` attributes before each file so that the parent's per-file "
            "stats merge does not double-count messages when a single worker process "
            "is reused across multiple files."
        ),
        "ground_truth_target": "_worker_check_single_file",
        "ground_truth_code": PYLINT_WORKER_CHECK_BODY,
        "source_repo": "pylint-dev/pylint",
        "source_publication_date": "2026-05-07",
        "source_license": "GPL-2.0",
        "difficulty_quartile": "q3",  # 45-line body
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-007",
        "tier": "public",
        "text": (
            "In pylint, find the FormatChecker method that walks a chunk of "
            "source-text lines and emits the `missing-final-newline`, "
            "`trailing-whitespace`, and `line-too-long` warnings. The method "
            "short-circuits when no line in the chunk exceeds `max-line-length`, "
            "otherwise strips `# pylint: disable` directive text from the lines so "
            "the directive itself does not inflate the length count, then "
            "optionally applies the user's `ignore-pattern-in-long-lines` regex to "
            "subtract additional text (for example to exclude URLs or long string "
            "literals) before measuring per-line length."
        ),
        "ground_truth_target": "check_lines",
        "ground_truth_code": PYLINT_CHECK_LINES_BODY,
        "source_repo": "pylint-dev/pylint",
        "source_publication_date": "2026-02-07",
        "source_license": "GPL-2.0",
        "difficulty_quartile": "q4",  # 59-line body, complex control flow
        "primary_server": "oci",
    },

    # ============================================================
    # saulpw/visidata  (GPL-3.0)
    # ============================================================
    {
        "query_id": "v1-pub-002",
        "tier": "public",
        "text": (
            "In visidata, find the loader helper generator that wraps a file-like "
            "object and yields data chunks using a self-tuning buffer: when the "
            "buffer fills faster than the target fill rate the buffer size doubles, "
            "otherwise the buffer is scaled down in proportion to the measured read "
            "time so TSV-style streams stay responsive without thrashing on slow inputs."
        ),
        "ground_truth_target": "adaptive_bufferer",
        "ground_truth_code": VISIDATA_ADAPTIVE_BUFFERER_BODY,
        "source_repo": "saulpw/visidata",
        "source_publication_date": "2026-04-18",
        "source_license": "GPL-3.0",
        "difficulty_quartile": "q2",
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-008",
        "tier": "public",
        "text": (
            "In visidata, find the entrypoint function for the seaborn-backed "
            "plot command that takes a chunk of rows and one or more x/y "
            "columns. The function imports `matplotlib.pyplot` and `seaborn` "
            "once in the originating visidata process via `vd.importExternal`, "
            "stores them in module-level globals so subsequent plots reuse "
            "them, then spawns a `multiprocessing.Process` targeting the "
            "actual rendering routine. The hoisted-import pattern matters "
            "because re-importing seaborn on every plot call would otherwise "
            "add several seconds of latency per plot."
        ),
        "ground_truth_target": "plot_seaborn",
        "ground_truth_code": VISIDATA_PLOT_SEABORN_BODY,
        "source_repo": "saulpw/visidata",
        "source_publication_date": "2026-05-23",
        "source_license": "GPL-3.0",
        "difficulty_quartile": "q1",  # 10-line body
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-009",
        "tier": "public",
        "text": (
            "In visidata, find the FreqTableSheet method that, when a single "
            "bin row on the frequency table is selected, propagates the "
            "selection to every source row that contributed to that bin. The "
            "method iterates the bin's `sourcerows` under a `Progress(...)` "
            "indicator so a bin with thousands of rows shows a progress bar, "
            "then delegates to the parent class via `super()` to also mark "
            "the bin itself as selected on the freqtbl sheet. Per the "
            "method's documented contract no undo record is created for the "
            "source-row selections; the caller is responsible for that."
        ),
        "ground_truth_target": "selectRow",
        "ground_truth_code": VISIDATA_FREQTBL_SELECTROW_BODY,
        "source_repo": "saulpw/visidata",
        "source_publication_date": "2026-05-20",
        "source_license": "GPL-3.0",
        "difficulty_quartile": "q1",  # 5-line body
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-010",
        "tier": "public",
        "text": (
            "In visidata, find the generator function in the save subsystem "
            "that walks every row in a sheet and yields an OrderedDict "
            "mapping column to display value, optionally with formatter "
            "applied. The function builds a per-column transformer chain "
            "(type cast, format function, delimiter-substitution table) up "
            "front, then per-row calls `col.getValue(r)` and threads the "
            "value through the chain. It treats None, `TypedExceptionWrapper`, "
            "`TypedWrapper`, and NaN floats (recognized via the `v != v` "
            "self-inequality trick) as empty/null values, so output formats "
            "like TSV and CSV do not emit literal `nan` strings for "
            "pandas-style missing values."
        ),
        "ground_truth_target": "iterdispvals",
        "ground_truth_code": VISIDATA_ITERDISPVALS_BODY,
        "source_repo": "saulpw/visidata",
        "source_publication_date": "2026-02-21",
        "source_license": "GPL-3.0",
        "difficulty_quartile": "q3",  # 46-line body
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-011",
        "tier": "public",
        "text": (
            "In visidata, find the helper function used by the `addcol-expr` "
            "command (bound to the `=` keystroke) that accepts the user's "
            "input string and returns an `ExprColumn`. If the input has the "
            "form `name = expression`, where `name` is a valid Python "
            "identifier and the right-hand side does not start with another "
            "`=` character (so that comparison operators like `==`, `>=`, "
            "`<=`, `!=` are not misinterpreted as assignment), the function "
            "uses the left side as the column name and the right side as "
            "the expression body; otherwise the entire input is used as "
            "both name and expression."
        ),
        "ground_truth_target": "addcol_expr",
        "ground_truth_code": VISIDATA_ADDCOL_EXPR_BODY,
        "source_repo": "saulpw/visidata",
        "source_publication_date": "2026-03-17",
        "source_license": "GPL-3.0",
        "difficulty_quartile": "q1",  # 12-line body
        "primary_server": "oci",
    },

    # ============================================================
    # buildbot/buildbot  (GPL-2.0)  -- public tier only (no post-2026-04-30 activity)
    # ============================================================
    {
        "query_id": "v1-pub-013",
        "tier": "public",
        "text": (
            "In buildbot, find the `WarningCountingShellCommand` method that "
            "loads the user-configured warning-suppression rules into the "
            "running build step. The method handles two input forms: an "
            "inline `suppressionList` is added directly, and a remote "
            "`suppressionFile` is streamed from the worker to a temporary "
            "file on the master via `remotetransfer.FileWriter` (so the "
            "entire file does not have to be loaded into the master's "
            "memory at once) and then parsed on a background thread via "
            "`deferToThread` to keep the master's event loop responsive. "
            "The method is a Twisted `inlineCallbacks` generator and "
            "includes back-compatibility for older worker versions that "
            "expect the `slavesrc` parameter name instead of the newer "
            "`workersrc`."
        ),
        "ground_truth_target": "setup_suppression",
        "ground_truth_code": BUILDBOT_SETUP_SUPPRESSION_BODY,
        "source_repo": "buildbot/buildbot",
        "source_publication_date": "2026-03-03",
        "source_license": "GPL-2.0",
        "difficulty_quartile": "q3",  # 35-line body
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-014",
        "tier": "public",
        "text": (
            "In buildbot, find the module-level async helper in the web "
            "config module that returns a boolean indicating whether a "
            "given user is allowed any access at all under the "
            "buildmaster's `Authz` policy. The helper delegates to "
            "`auth.assert_user_allowed_any_access(authz, user_info)` "
            "wrapped via the project's `any_to_async` adapter so the "
            "underlying check can be used from async code, and returns "
            "True if the check completes normally or False if any "
            "exception is raised. The result feeds the frontend `/config` "
            "payload so the single-page app knows whether the visiting "
            "user has at least some access to the buildmaster."
        ),
        "ground_truth_target": "_get_any_access_allowed",
        "ground_truth_code": BUILDBOT_GET_ANY_ACCESS_BODY,
        "source_repo": "buildbot/buildbot",
        "source_publication_date": "2026-02-26",
        "source_license": "GPL-2.0",
        "difficulty_quartile": "q1",  # 6-line body
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-015",
        "tier": "public",
        "text": (
            "In buildbot, find the build-step method on `Trigger` that "
            "orchestrates triggering a list of other schedulers from "
            "inside a running build. The method calls "
            "`getSchedulersAndProperties()` to resolve the per-scheduler "
            "configuration (with back-compatibility for both the legacy "
            "two-tuple shape and the newer dict shape), then for each "
            "scheduler computes a propagation priority equal to the "
            "maximum priority across the current build's outstanding "
            "buildrequests so the triggered builds inherit that priority. "
            "It collects the `idsDeferred` and `resultsDeferred` returned "
            "from each `sch.trigger(...)` call, attaches URLs to each "
            "triggered buildrequest ID, and if `waitForFinish` is set "
            "awaits a `DeferredList` of all the result deferreds before "
            "returning an aggregate worst-status result."
        ),
        "ground_truth_target": "run",
        "ground_truth_code": BUILDBOT_TRIGGER_RUN_BODY,
        "source_repo": "buildbot/buildbot",
        "source_publication_date": "2026-03-03",
        "source_license": "GPL-2.0",
        "difficulty_quartile": "q4",  # 92-line body
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-016",
        "tier": "public",
        "text": (
            "In buildbot, find the WAMP-service callback that fires once "
            "the master has successfully joined a WAMP realm. The method "
            "logs the established connection along with the negotiated "
            "WAMP `authid` so master logs make the authenticated identity "
            "clear, then walks every registered service (itself plus its "
            "child services) and calls `register` and `subscribe` for "
            "each so RPC and pubsub bindings are established. Finally it "
            "publishes an `org.buildbot.<masterid>.connected` topic and "
            "resolves the parent service's `serviceDeferred` callback so "
            "other code paths waiting for the connection can proceed."
        ),
        "ground_truth_target": "onJoin",
        "ground_truth_code": BUILDBOT_ONJOIN_BODY,
        "source_repo": "buildbot/buildbot",
        "source_publication_date": "2026-02-25",
        "source_license": "GPL-2.0",
        "difficulty_quartile": "q1",  # 8-line body
        "primary_server": "oci",
    },

    # ============================================================
    # psycopg/psycopg  (LGPL-3.0 → schema "LGPL")
    # ============================================================
    {
        "query_id": "v1-pub-003",
        "tier": "public",
        "text": (
            "In psycopg, find the cursor-base coroutine that handles the prepared-"
            "statement path: it decides whether the query has been prepared already, "
            "sends `Parse` when preparation is needed, and on the Parse/Sync exchange "
            "must iterate through every returned PGresult and raise the appropriate "
            "psycopg error if any result has FATAL_ERROR status (covering the "
            "ErrorResponse-during-Sync case the PostgreSQL wire protocol allows)."
        ),
        "ground_truth_target": "_maybe_prepare_gen",
        "ground_truth_code": PSYCOPG_MAYBE_PREPARE_GEN_BODY,
        "source_repo": "psycopg/psycopg",
        "source_publication_date": "2026-02-18",
        "source_license": "LGPL",
        "difficulty_quartile": "q3",
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-012",
        "tier": "public",
        "text": (
            "In psycopg, find the `PrepareManager` method that decides whether "
            "the entire prepared-statement cache must be invalidated after a "
            "query has completed. The method walks the libpq `PGresult` objects "
            "returned by the server and checks each one's `command_status` bytes "
            "against a pre-compiled regex of PostgreSQL commands that can "
            "invalidate cached plans (`DROP`, `ALTER`, `ROLLBACK`, `DISCARD`). "
            "If any matching command status is seen, the method clears the cache "
            "by delegating to the manager's `clear()` helper and returns its "
            "result; otherwise it returns False. The method only iterates "
            "results when the cache already has named entries or the current "
            "query was selected for preparation."
        ),
        "ground_truth_target": "_should_discard",
        "ground_truth_code": PSYCOPG_SHOULD_DISCARD_BODY,
        "source_repo": "psycopg/psycopg",
        "source_publication_date": "2026-05-21",
        "source_license": "LGPL",
        "difficulty_quartile": "q2",  # 17-line body, semantically denser than visidata q1's
        "primary_server": "oci",
    },

    # ============================================================
    # archlinux/archinstall  (GPL-3.0)
    # ============================================================
    {
        "query_id": "v1-pub-017",
        "tier": "public",
        "text": (
            "In archinstall, find the Installer method that sets a user's "
            "login shell during a chroot install. The method must avoid the "
            "shell-injection risk of interpolating the username and shell "
            "path into a `sh -c` command line, so it builds an explicit argv "
            "list and invokes `arch-chroot` with `-S` plus `chsh -s <shell> "
            "<user>` arguments, then runs the subprocess directly. On "
            "`CalledProcessError` it logs the error via the debug channel "
            "and returns False; on success it returns True."
        ),
        "ground_truth_target": "user_set_shell",
        "ground_truth_code": ARCHINSTALL_USER_SET_SHELL_BODY,
        "source_repo": "archlinux/archinstall",
        "source_publication_date": "2026-04-20",
        "source_license": "GPL-3.0",
        "difficulty_quartile": "q1",  # 7-line body, shell-injection fix
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-018",
        "tier": "public",
        "text": (
            "In archinstall, find the `GfxDriver` enum method that "
            "distinguishes Nvidia drivers shipping proprietary userspace "
            "components from those that are fully open. The method exists "
            "because the Sway compositor does not support proprietary Nvidia "
            "userspace but does work with nouveau, so the install flow needs "
            "a way to gate the sway+proprietary confirmation dialog. The "
            "implementation matches on the enum value and returns True only "
            "for the open-kernel-module-plus-proprietary-userspace variant "
            "(the `nvidia-open-dkms` package family); every other GfxDriver "
            "value returns False."
        ),
        "ground_truth_target": "is_nvidia_proprietary",
        "ground_truth_code": ARCHINSTALL_IS_NVIDIA_PROPRIETARY_BODY,
        "source_repo": "archlinux/archinstall",
        "source_publication_date": "2026-04-28",
        "source_license": "GPL-3.0",
        "difficulty_quartile": "q1",  # ~10 lines incl docstring; single match-case
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-019",
        "tier": "public",
        "text": (
            "In archinstall, find the `ConfigurationOutput` method that "
            "renders a concise human-readable summary of the current "
            "installation configuration. The method builds a list of "
            "(label, value) tuples by walking each configuration section "
            "the user can touch (disk modifications with filesystem type "
            "and a LUKS marker per disk if disk-level encryption is enabled, "
            "bootloader, kernels, profile and greeter, packages count, "
            "network configuration type, locale, and timezone), skipping "
            "any section that is unset. After the rows are collected it "
            "computes the maximum translated label width plus two "
            "characters of padding and renders each row as a left-aligned "
            "label column followed by the value, joined by newlines. "
            "Returns an empty string when no section has data."
        ),
        "ground_truth_target": "as_summary",
        "ground_truth_code": ARCHINSTALL_AS_SUMMARY_BODY,
        "source_repo": "archlinux/archinstall",
        "source_publication_date": "2026-04-28",
        "source_license": "GPL-3.0",
        "difficulty_quartile": "q3",  # 60-line body, sequential population
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-020",
        "tier": "public",
        "text": (
            "In archinstall, find the `BspwmProfile` method that runs after "
            "package install to put each new user into a working bspwm "
            "session. The method walks the list of users and for each one "
            "calls into the installer's `arch_chroot` helper with "
            "`run_as=user.username`: first creates `~/.config/bspwm` and "
            "`~/.config/sxhkd` directories, then copies the example "
            "`bspwmrc` and `sxhkdrc` config files out of "
            "`/usr/share/doc/bspwm/examples/` into those directories, and "
            "finally `chmod +x` the bspwmrc so it is executable. The method "
            "exists to fix a black screen on first login when no per-user "
            "configs were present."
        ),
        "ground_truth_target": "provision",
        "ground_truth_code": ARCHINSTALL_BSPWM_PROVISION_BODY,
        "source_repo": "archlinux/archinstall",
        "source_publication_date": "2026-05-07",
        "source_license": "GPL-3.0",
        "difficulty_quartile": "q1",  # 8-line override; concrete mkdir+cp+chmod sequence
        "primary_server": "oci",
    },
    {
        "query_id": "v1-pub-021",
        "tier": "public",
        "text": (
            "In archinstall, find the module-level async function in the "
            "locale menu module that prompts the user to choose a console "
            "font. It enumerates the available fonts by calling the "
            "`list_console_fonts` helper, wraps each font name in a "
            "`MenuItem` with the same string as both label and value, "
            "builds a `MenuItemGroup` with sort disabled, focuses on any "
            "preset value passed in, and shows a filter-enabled selection "
            "menu titled 'Console font'. On a Selection result it returns "
            "the chosen font; on Skip it returns the preset unchanged; on "
            "any other result type it raises a ValueError."
        ),
        "ground_truth_target": "select_console_font",
        "ground_truth_code": ARCHINSTALL_SELECT_CONSOLE_FONT_BODY,
        "source_repo": "archlinux/archinstall",
        "source_publication_date": "2026-04-26",
        "source_license": "GPL-3.0",
        "difficulty_quartile": "q2",  # 22-line async; mechanical menu flow
        "primary_server": "oci",
    },
]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mining.build_v1")
    p.add_argument("--offline", action="store_true", help="skip gh code search; emit empty audits")
    p.add_argument("--max-ngrams", type=int, default=20)
    p.add_argument("--sleep", type=float, default=2.0)
    p.add_argument(
        "--output", type=Path, default=Path("tasks/v1/queries.jsonl"),
        help="output JSONL path (overwrites)",
    )
    args = p.parse_args(argv)

    out_lines: list[str] = []
    for row in PILOT_ROWS:
        print(f"[{row['query_id']}] computing 5-gram audit (online={not args.offline})...")
        audit = compute_audit(
            row["ground_truth_code"],
            max_ngrams=args.max_ngrams,
            sleep_between=args.sleep,
            online=not args.offline,
        )
        hit_count = sum(1 for r in audit if r["github_hits"] >= 1 or r["web_hits"] >= 1)
        print(f"[{row['query_id']}] {len(audit)} ngrams audited; {hit_count} hit ≥1 public source")
        full_row = {**row, "fivegram_audit": audit}
        out_lines.append(json.dumps(full_row, ensure_ascii=False))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"\nWrote {len(out_lines)} v1 public-tier rows to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
