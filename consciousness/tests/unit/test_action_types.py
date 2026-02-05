"""Tests for action types."""

import pytest
from sociopsi.actions.action_types import ActionDefinition


def test_action_definition_initialization():
    """Test ActionDefinition initialization."""

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action description",
        parameters={"param1": {"type": "string", "required": True}},
        conflicts_with=["other_action"],
        estimated_duration=2.5,
        execute=dummy_execute,
    )

    assert action.name == "test_action"
    assert action.description == "Test action description"
    assert "param1" in action.parameters
    assert "other_action" in action.conflicts_with
    assert action.estimated_duration == 2.5
    assert action.execute == dummy_execute


def test_action_definition_defaults():
    """Test ActionDefinition default values."""

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action",
        parameters={},
        execute=dummy_execute,
    )

    assert action.conflicts_with == []
    assert action.estimated_duration == 1.0


def test_get_param_schema_summary():
    """Test parameter schema summary generation."""

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action",
        parameters={
            "param1": {"type": "string", "required": True},
            "param2": {"type": "number", "required": False},
            "param3": {"type": "boolean", "required": True},
        },
        execute=dummy_execute,
    )

    summary = action.get_param_schema_summary()
    assert "param1: string (required)" in summary
    assert "param2: number (optional)" in summary
    assert "param3: boolean (required)" in summary


def test_get_param_schema_summary_no_params():
    """Test schema summary with no parameters."""

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action",
        parameters={},
        execute=dummy_execute,
    )

    summary = action.get_param_schema_summary()
    assert summary == "no parameters"


def test_validate_parameters_valid():
    """Test validating valid parameters."""

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action",
        parameters={
            "text": {"type": "string", "required": True},
            "count": {"type": "number", "required": False},
        },
        execute=dummy_execute,
    )

    # Valid with all params
    valid, error = action.validate_parameters({"text": "hello", "count": 5})
    assert valid
    assert error is None

    # Valid with only required params
    valid, error = action.validate_parameters({"text": "hello"})
    assert valid
    assert error is None


def test_validate_parameters_missing_required():
    """Test validation fails when required parameter missing."""

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action",
        parameters={
            "text": {"type": "string", "required": True},
            "count": {"type": "number", "required": False},
        },
        execute=dummy_execute,
    )

    valid, error = action.validate_parameters({"count": 5})
    assert not valid
    assert "Missing required parameter: text" in error


def test_validate_parameters_unknown_param():
    """Test validation fails with unknown parameter."""

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action",
        parameters={
            "text": {"type": "string", "required": True},
        },
        execute=dummy_execute,
    )

    valid, error = action.validate_parameters({"text": "hello", "unknown": "value"})
    assert not valid
    assert "Unknown parameter: unknown" in error


def test_validate_parameters_wrong_type_string():
    """Test validation fails with wrong type for string parameter."""

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action",
        parameters={
            "text": {"type": "string", "required": True},
        },
        execute=dummy_execute,
    )

    valid, error = action.validate_parameters({"text": 123})
    assert not valid
    assert "must be a string" in error


def test_validate_parameters_wrong_type_number():
    """Test validation fails with wrong type for number parameter."""

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action",
        parameters={
            "count": {"type": "number", "required": True},
        },
        execute=dummy_execute,
    )

    valid, error = action.validate_parameters({"count": "not a number"})
    assert not valid
    assert "must be a number" in error


def test_validate_parameters_wrong_type_boolean():
    """Test validation fails with wrong type for boolean parameter."""

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action",
        parameters={
            "flag": {"type": "boolean", "required": True},
        },
        execute=dummy_execute,
    )

    valid, error = action.validate_parameters({"flag": "not a boolean"})
    assert not valid
    assert "must be a boolean" in error


def test_validate_parameters_number_accepts_int_and_float():
    """Test number type accepts both int and float."""

    async def dummy_execute():
        pass

    action = ActionDefinition(
        name="test_action",
        description="Test action",
        parameters={
            "value": {"type": "number", "required": True},
        },
        execute=dummy_execute,
    )

    # Integer should be valid
    valid, error = action.validate_parameters({"value": 42})
    assert valid
    assert error is None

    # Float should be valid
    valid, error = action.validate_parameters({"value": 3.14})
    assert valid
    assert error is None
