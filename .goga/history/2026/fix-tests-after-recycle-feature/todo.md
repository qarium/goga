## python 3.10

```
=================================== FAILURES ===================================
_________ TestFlowRepeatContract.test_flow_repeat_kw_only_params_true __________
/home/runner/work/goga/goga/tests/pipeline/compiler/test_flow_repeat_contract.py:68: in test_flow_repeat_kw_only_params_true
    assert FlowRepeat.__dataclass_params__.kw_only is True
E   AttributeError: '_DataclassParams' object has no attribute 'kw_only'
_____ TestWorkflowRepeatContract.test_workflow_repeat_is_kw_only_dataclass _____
/home/runner/work/goga/goga/tests/pipeline/workflow/test_workflow_repeat_contract.py:36: in test_workflow_repeat_is_kw_only_dataclass
    assert WorkflowRepeat.__dataclass_params__.kw_only is True
E   AttributeError: '_DataclassParams' object has no attribute 'kw_only'
=============================== warnings summary ===============================
tests/commands/test_usages.py: 21 warnings
tests/integration/test_config_hooks_passthrough.py: 4 warnings
tests/usages/status/test_config_checkpoint.py: 2 warnings
  /home/runner/work/goga/goga/goga/commands/usages/usages.py:150: DeprecationWarning: 'get_text_stream' is deprecated and will be removed in Click 9.0.
    color = click.get_text_stream("stdout").isatty()

tests/test_cli.py::TestSchemaLintCoexist::test_cli_schema_lint_coexist
  /home/runner/work/goga/goga/tests/test_cli.py:310: DeprecationWarning: 'isolated_filesystem' is deprecated and will be removed in Click 9.0. Use 'tempfile.TemporaryDirectory' or pytest's 'tmp_path' fixture with absolute paths instead.
    with runner.isolated_filesystem() as tmp:

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/pipeline/compiler/test_flow_repeat_contract.py::TestFlowRepeatContract::test_flow_repeat_kw_only_params_true - AttributeError: '_DataclassParams' object has no attribute 'kw_only'
FAILED tests/pipeline/workflow/test_workflow_repeat_contract.py::TestWorkflowRepeatContract::test_workflow_repeat_is_kw_only_dataclass - AttributeError: '_DataclassParams' object has no attribute 'kw_only'
================= 2 failed, 7890 passed, 28 warnings in 53.21s =================
```

## python 3.11

```
=================================== FAILURES ===================================
_________ TestFlowRepeatContract.test_flow_repeat_kw_only_params_true __________
/home/runner/work/goga/goga/tests/pipeline/compiler/test_flow_repeat_contract.py:68: in test_flow_repeat_kw_only_params_true
    assert FlowRepeat.__dataclass_params__.kw_only is True
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: '_DataclassParams' object has no attribute 'kw_only'
_____ TestWorkflowRepeatContract.test_workflow_repeat_is_kw_only_dataclass _____
/home/runner/work/goga/goga/tests/pipeline/workflow/test_workflow_repeat_contract.py:36: in test_workflow_repeat_is_kw_only_dataclass
    assert WorkflowRepeat.__dataclass_params__.kw_only is True
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: '_DataclassParams' object has no attribute 'kw_only'
=============================== warnings summary ===============================
tests/commands/test_usages.py: 21 warnings
tests/integration/test_config_hooks_passthrough.py: 4 warnings
tests/usages/status/test_config_checkpoint.py: 2 warnings
  /home/runner/work/goga/goga/goga/commands/usages/usages.py:150: DeprecationWarning: 'get_text_stream' is deprecated and will be removed in Click 9.0.
    color = click.get_text_stream("stdout").isatty()

tests/test_cli.py::TestSchemaLintCoexist::test_cli_schema_lint_coexist
  /home/runner/work/goga/goga/tests/test_cli.py:310: DeprecationWarning: 'isolated_filesystem' is deprecated and will be removed in Click 9.0. Use 'tempfile.TemporaryDirectory' or pytest's 'tmp_path' fixture with absolute paths instead.
    with runner.isolated_filesystem() as tmp:

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/pipeline/compiler/test_flow_repeat_contract.py::TestFlowRepeatContract::test_flow_repeat_kw_only_params_true - AttributeError: '_DataclassParams' object has no attribute 'kw_only'
FAILED tests/pipeline/workflow/test_workflow_repeat_contract.py::TestWorkflowRepeatContract::test_workflow_repeat_is_kw_only_dataclass - AttributeError: '_DataclassParams' object has no attribute 'kw_only'
============ 2 failed, 7890 passed, 28 warnings in 71.57s (0:01:11) ============
```