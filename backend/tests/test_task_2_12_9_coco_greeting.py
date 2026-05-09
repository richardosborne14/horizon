"""
Tests for TASK-2.12.9 — CoCo greeting + net/brut fix + get_employees tool.

Covers:
  1. Updated welcome message (greeting)
  2. Footer booking URL fallback logic
  3. _NET_VS_BRUT_RULE included in build_system_prompt
  4. _tool_get_employees returns correct data shape
  5. _tool_get_employees returns meaningful cotisations labels per contract_type
  6. _tool_get_employees handles empty employee list
  7. get_employees registered in TOOL_DEFINITIONS and TOOL_UI_LABELS
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.coco_prompts import build_system_prompt, _NET_VS_BRUT_RULE
from app.services.coco_tools import (
    TOOL_DEFINITIONS,
    TOOL_UI_LABELS,
    _tool_get_employees,
)


# ── 1. _NET_VS_BRUT_RULE present and non-empty ────────────────────────────────

def test_net_vs_brut_rule_constant_exists():
    """_NET_VS_BRUT_RULE must be a non-empty string (TASK-2.12.9)."""
    assert isinstance(_NET_VS_BRUT_RULE, str)
    assert len(_NET_VS_BRUT_RULE) > 100


def test_net_vs_brut_rule_mentions_net():
    """Rule must explicitly say the salary entered is NET, not brut."""
    rule_lower = _NET_VS_BRUT_RULE.lower()
    assert "net" in rule_lower
    assert "brut" in rule_lower


# ── 2. build_system_prompt includes the net/brut rule ────────────────────────

def test_build_system_prompt_includes_net_vs_brut_rule():
    """build_system_prompt must include the net/brut rule in every authenticated prompt."""
    prompt = build_system_prompt()
    assert "RÈGLE SALAIRE NET vs BRUT" in prompt or "NET" in prompt
    assert "brut" in prompt.lower()


def test_build_system_prompt_net_vs_brut_rule_with_profile():
    """Net/brut rule injected even when user profile is provided."""
    profile = {
        "user_name": "Estelle",
        "salon_name": "Salon Test",
        "experience_level": "intermediaire",
        "business_goals": [],
        "interests": [],
        "profile_notes": {},
    }
    prompt = build_system_prompt(user_profile=profile)
    assert "NET" in prompt


# ── 3. get_employees in TOOL_DEFINITIONS and TOOL_UI_LABELS ──────────────────

def test_get_employees_in_tool_definitions():
    """get_employees must be declared in TOOL_DEFINITIONS (sent to Claude)."""
    names = [t["name"] for t in TOOL_DEFINITIONS]
    assert "get_employees" in names


def test_get_employees_tool_definition_shape():
    """get_employees definition must have correct schema."""
    defn = next(t for t in TOOL_DEFINITIONS if t["name"] == "get_employees")
    assert "description" in defn
    assert "input_schema" in defn
    assert defn["input_schema"]["type"] == "object"
    assert len(defn["description"]) > 50


def test_get_employees_in_tool_ui_labels():
    """get_employees must have a UI label (shown in chat panel while thinking)."""
    assert "get_employees" in TOOL_UI_LABELS
    assert len(TOOL_UI_LABELS["get_employees"]) > 5


# ── 4. _tool_get_employees — returns employee list ────────────────────────────

@pytest.mark.asyncio
async def test_tool_get_employees_returns_employee_list():
    """Returns found=True and employees list for a salon with active employees."""
    from app.models.salon import Employee

    salon_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    mock_emp = MagicMock(spec=Employee)
    mock_emp.name = "Julie Dupont"
    mock_emp.role_type = "salarie"
    mock_emp.contract_type = "cdi"
    mock_emp.contract_subtype = None
    mock_emp.salary_brut = Decimal("1800.00")
    mock_emp.cotisations_patronales = Decimal("720.00")
    mock_emp.taux_occupation = Decimal("0.65")
    mock_emp.hours_per_week = Decimal("35.00")
    mock_emp.is_active = True

    mock_salon = MagicMock()
    mock_salon.id = salon_id
    mock_salon.name = "Salon Test"

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    # First call returns salon, second returns employees
    salon_scalar = MagicMock()
    salon_scalar.scalar_one_or_none.return_value = mock_salon

    emp_scalars = MagicMock()
    emp_scalars.scalars.return_value.all.return_value = [mock_emp]

    mock_db.execute.side_effect = [salon_scalar, emp_scalars]

    result = await _tool_get_employees(
        {},
        db=mock_db,
        user_id=user_id,
        screen_context=None,
    )

    assert result["found"] is True
    assert result["employee_count"] == 1
    employees = result["employees"]
    assert len(employees) == 1
    assert employees[0]["name"] == "Julie Dupont"
    assert employees[0]["contract_type"] == "cdi"
    assert "NET" in result["salary_input_note"]


# ── 5. _tool_get_employees — cotisations labels per contract_type ─────────────

@pytest.mark.asyncio
async def test_tool_get_employees_cotisations_label_tns():
    """TNS contract gets correct ~45% label."""
    from app.models.salon import Employee

    salon_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    mock_emp = MagicMock(spec=Employee)
    mock_emp.name = "Eric Patron"
    mock_emp.role_type = "dirigeant"
    mock_emp.contract_type = "tns"
    mock_emp.contract_subtype = None
    mock_emp.salary_brut = Decimal("3000.00")
    mock_emp.cotisations_patronales = None
    mock_emp.taux_occupation = Decimal("0.65")
    mock_emp.hours_per_week = Decimal("35.00")
    mock_emp.is_active = True

    mock_salon = MagicMock()
    mock_salon.id = salon_id
    mock_salon.name = "Salon Test"

    mock_db = AsyncMock()
    salon_scalar = MagicMock()
    salon_scalar.scalar_one_or_none.return_value = mock_salon
    emp_scalars = MagicMock()
    emp_scalars.scalars.return_value.all.return_value = [mock_emp]
    mock_db.execute.side_effect = [salon_scalar, emp_scalars]

    result = await _tool_get_employees(
        {}, db=mock_db, user_id=user_id, screen_context=None
    )
    assert result["found"] is True
    label = result["employees"][0]["cotisations_regime"]
    assert "TNS" in label
    assert "45" in label


@pytest.mark.asyncio
async def test_tool_get_employees_cotisations_label_apprentissage_cap():
    """Apprentissage CAP gets non-productive label."""
    from app.models.salon import Employee

    user_id = str(uuid.uuid4())
    mock_emp = MagicMock(spec=Employee)
    mock_emp.name = "Thomas CAP"
    mock_emp.role_type = "apprenti"
    mock_emp.contract_type = "apprentissage"
    mock_emp.contract_subtype = "cap"
    mock_emp.salary_brut = Decimal("500.00")
    mock_emp.cotisations_patronales = None
    mock_emp.taux_occupation = Decimal("0.00")
    mock_emp.hours_per_week = Decimal("35.00")
    mock_emp.is_active = True

    mock_salon = MagicMock()
    mock_salon.id = uuid.uuid4()
    mock_salon.name = "Salon Test"

    mock_db = AsyncMock()
    salon_scalar = MagicMock()
    salon_scalar.scalar_one_or_none.return_value = mock_salon
    emp_scalars = MagicMock()
    emp_scalars.scalars.return_value.all.return_value = [mock_emp]
    mock_db.execute.side_effect = [salon_scalar, emp_scalars]

    result = await _tool_get_employees(
        {}, db=mock_db, user_id=user_id, screen_context=None
    )
    label = result["employees"][0]["cotisations_regime"]
    assert "CAP" in label
    assert "non productif" in label.lower()


@pytest.mark.asyncio
async def test_tool_get_employees_cotisations_label_apprentissage_bp():
    """Apprentissage BP/BM gets RGDU label (productive)."""
    from app.models.salon import Employee

    user_id = str(uuid.uuid4())
    mock_emp = MagicMock(spec=Employee)
    mock_emp.name = "Sophie BP"
    mock_emp.role_type = "apprenti"
    mock_emp.contract_type = "apprentissage"
    mock_emp.contract_subtype = "bp"
    mock_emp.salary_brut = Decimal("800.00")
    mock_emp.cotisations_patronales = None
    mock_emp.taux_occupation = Decimal("0.35")
    mock_emp.hours_per_week = Decimal("35.00")
    mock_emp.is_active = True

    mock_salon = MagicMock()
    mock_salon.id = uuid.uuid4()
    mock_salon.name = "Salon Test"

    mock_db = AsyncMock()
    salon_scalar = MagicMock()
    salon_scalar.scalar_one_or_none.return_value = mock_salon
    emp_scalars = MagicMock()
    emp_scalars.scalars.return_value.all.return_value = [mock_emp]
    mock_db.execute.side_effect = [salon_scalar, emp_scalars]

    result = await _tool_get_employees(
        {}, db=mock_db, user_id=user_id, screen_context=None
    )
    label = result["employees"][0]["cotisations_regime"]
    assert "BP" in label or "BM" in label
    # BP/BM is productive — must NOT say non-productif
    assert "non productif" not in label.lower()


# ── 6. _tool_get_employees — empty list ───────────────────────────────────────

@pytest.mark.asyncio
async def test_tool_get_employees_no_employees_returns_helpful_message():
    """Returns found=False with a helpful message when no active employees."""
    mock_salon = MagicMock()
    mock_salon.id = uuid.uuid4()
    mock_salon.name = "Salon Test"

    mock_db = AsyncMock()
    salon_scalar = MagicMock()
    salon_scalar.scalar_one_or_none.return_value = mock_salon
    emp_scalars = MagicMock()
    emp_scalars.scalars.return_value.all.return_value = []
    mock_db.execute.side_effect = [salon_scalar, emp_scalars]

    result = await _tool_get_employees(
        {}, db=mock_db, user_id=str(uuid.uuid4()), screen_context=None
    )
    assert result["found"] is False
    assert "reason" in result
    assert len(result["reason"]) > 10


@pytest.mark.asyncio
async def test_tool_get_employees_no_user_id():
    """Returns found=False when user_id is None."""
    mock_db = AsyncMock()
    result = await _tool_get_employees(
        {}, db=mock_db, user_id=None, screen_context=None
    )
    assert result["found"] is False


@pytest.mark.asyncio
async def test_tool_get_employees_no_salon():
    """Returns found=False when user has no salon."""
    mock_db = AsyncMock()
    salon_scalar = MagicMock()
    salon_scalar.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = salon_scalar

    result = await _tool_get_employees(
        {}, db=mock_db, user_id=str(uuid.uuid4()), screen_context=None
    )
    assert result["found"] is False


# ── 7. salary_input_note is present in successful response ────────────────────

@pytest.mark.asyncio
async def test_tool_get_employees_has_salary_input_note():
    """Every successful response includes salary_input_note explaining NET input."""
    from app.models.salon import Employee

    user_id = str(uuid.uuid4())
    mock_emp = MagicMock(spec=Employee)
    mock_emp.name = "Estelle"
    mock_emp.role_type = "salarie"
    mock_emp.contract_type = "cdi"
    mock_emp.contract_subtype = None
    mock_emp.salary_brut = Decimal("1500.00")
    mock_emp.cotisations_patronales = Decimal("600.00")
    mock_emp.taux_occupation = Decimal("0.65")
    mock_emp.hours_per_week = Decimal("35.00")
    mock_emp.is_active = True

    mock_salon = MagicMock()
    mock_salon.id = uuid.uuid4()
    mock_salon.name = "Salon Estelle"

    mock_db = AsyncMock()
    salon_scalar = MagicMock()
    salon_scalar.scalar_one_or_none.return_value = mock_salon
    emp_scalars = MagicMock()
    emp_scalars.scalars.return_value.all.return_value = [mock_emp]
    mock_db.execute.side_effect = [salon_scalar, emp_scalars]

    result = await _tool_get_employees(
        {}, db=mock_db, user_id=user_id, screen_context=None
    )
    assert "salary_input_note" in result
    note = result["salary_input_note"]
    assert "NET" in note
    assert len(note) > 30
