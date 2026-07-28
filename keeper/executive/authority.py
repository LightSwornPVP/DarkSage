from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import re

from keeper.executive.enums import (
    ActionCategory,
    ApprovalKind,
    AuthorityOutcome,
    DelegationMode,
    ExecutiveState,
)
from keeper.executive.models import (
    ApprovalRecord,
    AuthorityDecision,
    ExecutiveTask,
    ProjectCharter,
    ProjectRecord,
    ProposedAction,
    SpecialistProfile,
)


NON_DELEGABLE = frozenset(
    {
        ActionCategory.DELETE_PROTECTED,
        ActionCategory.REWRITE_HISTORY,
        ActionCategory.ACCESS_CREDENTIAL,
        ActionCategory.CHANGE_SECURITY_BOUNDARY,
        ActionCategory.ENABLE_LIVE_TRADING,
        ActionCategory.CHANGE_FINANCIAL_AUTHORITY,
        ActionCategory.CHANGE_GOVERNANCE,
        ActionCategory.IRREVERSIBLE_DESTRUCTIVE,
    }
)
SEPARATELY_APPROVABLE = frozenset(
    {
        ActionCategory.PUSH,
        ActionCategory.DEPLOY_PRODUCTION,
        ActionCategory.PUBLISH_EXTERNAL,
        ActionCategory.PURCHASE,
        ActionCategory.SPEND,
        ActionCategory.COMMIT,
    }
)
ADVISORY_ACTIONS = frozenset(
    {ActionCategory.ANALYZE, ActionCategory.PLAN, ActionCategory.DRAFT, ActionCategory.READ}
)
TERMINAL_STATES = frozenset(
    {ExecutiveState.COMPLETED, ExecutiveState.CANCELED, ExecutiveState.FAILED}
)


class AuthorityEvaluator:
    def evaluate(
        self,
        project: ProjectRecord,
        charter: ProjectCharter,
        action: ProposedAction,
        approvals: tuple[ApprovalRecord, ...] = (),
        *,
        now: datetime | None = None,
    ) -> AuthorityDecision:
        current_time = now or datetime.now(UTC)
        category = ActionCategory(action.category)
        if project.project_id != action.project_id or charter.project_id != project.project_id:
            return self._decision(AuthorityOutcome.INDETERMINATE, "identity-binding", "project_id", "project identity does not match", "reject the action")
        if ExecutiveState(project.state) in TERMINAL_STATES:
            return self._decision(AuthorityOutcome.DENIED, "terminal-project", "state", "terminal projects cannot launch actions", "create a new project")
        if ExecutiveState(project.state) in {
            ExecutiveState.PAUSED,
            ExecutiveState.BLOCKED,
            ExecutiveState.WAITING_FOR_FOUNDER,
            ExecutiveState.WAITING_FOR_PROVIDER,
            ExecutiveState.WAITING_FOR_CREDENTIAL,
            ExecutiveState.WAITING_FOR_EXTERNAL_SYSTEM,
            ExecutiveState.WAITING_FOR_USAGE_RESET,
        }:
            return self._decision(AuthorityOutcome.DENIED, "non-executable-project-state", "state", "the project is paused or waiting", "resolve the pause before launching work")
        if project.active_charter_revision != action.charter_revision or charter.revision != action.charter_revision:
            return self._decision(AuthorityOutcome.CHARTER_REVISION_REQUIRED, "active-revision", "revision", "action is bound to a stale charter revision", "bind the action to the active charter")
        if charter.status != "ACTIVE" or project.active_charter_id != charter.charter_id:
            return self._decision(AuthorityOutcome.DENIED, "active-charter", "status", "charter is not the active approved revision", "activate an approved charter")
        if charter.authority_envelope.expires_at is not None and datetime.fromisoformat(charter.authority_envelope.expires_at) <= current_time:
            return self._decision(AuthorityOutcome.EXPIRED, "envelope-expiration", "authority_envelope.expires_at", "charter authority has expired", "obtain a charter revision")
        if category in NON_DELEGABLE:
            return self._decision(AuthorityOutcome.DENIED, "non-delegable-action", "authority_envelope.denied_actions", "this action class cannot be delegated", "Founder must perform the action outside Keeper")
        if action.category in charter.authority_envelope.denied_actions:
            return self._decision(AuthorityOutcome.DENIED, "charter-denial", "authority_envelope.denied_actions", "the active charter explicitly denies this action", "revise the charter")
        if any(_action_matches_non_goal(action, item) for item in charter.non_goals):
            return self._decision(
                AuthorityOutcome.DENIED,
                "explicit-non-goal",
                "non_goals",
                "the action targets or materially contributes to an explicit non-goal",
                "remove the action or obtain a charter revision",
            )
        classification_error = self._classification_error(action)
        if classification_error is not None:
            return classification_error
        if category is ActionCategory.EXPAND_SCOPE or not set(action.scope).issubset(set(charter.deliverables)):
            return self._decision(AuthorityOutcome.CHARTER_REVISION_REQUIRED, "scope-containment", "deliverables", "the action expands or does not map to charter scope", "create a charter amendment")
        constraint_error = self._constraint_error(charter, action)
        if constraint_error is not None:
            return constraint_error
        approval = self._matching_approval(charter, action, approvals, current_time)
        if approval == "REVOKED":
            return self._decision(AuthorityOutcome.REVOKED, "approval-revocation", "approval.revoked_at", "matching authority was revoked", "pause and request new Founder direction")
        if approval == "EXPIRED":
            return self._decision(AuthorityOutcome.EXPIRED, "approval-expiration", "approval.expires_at", "matching approval expired", "request renewed Founder approval")
        if isinstance(approval, ApprovalRecord):
            return AuthorityDecision(
                AuthorityOutcome.ALLOWED_WITHIN_LIMIT.value,
                "bound-founder-approval",
                "approval",
                dict(approval.limits),
                "a current approval authorizes this action",
                "execute within the recorded limits",
                approval.approval_id,
            )
        mode = DelegationMode(charter.delegation_mode)
        if mode is DelegationMode.ADVISORY and category not in ADVISORY_ACTIONS:
            return self._decision(AuthorityOutcome.REQUIRES_FOUNDER_APPROVAL, "advisory-mode", "delegation_mode", "Advisory mode cannot execute material actions", "request one-time or charter approval")
        if category in SEPARATELY_APPROVABLE or action.external_side_effect:
            return self._decision(AuthorityOutcome.REQUIRES_FOUNDER_APPROVAL, "separate-approval", "authority_envelope.separately_approvable_actions", "the action requires separate Founder approval", "request a bound approval")
        if action.category not in charter.authority_envelope.allowed_actions:
            return self._decision(AuthorityOutcome.REQUIRES_FOUNDER_APPROVAL if mode is DelegationMode.DELEGATED else AuthorityOutcome.DENIED, "allowed-action-list", "authority_envelope.allowed_actions", "the action is not in the approved authority envelope", "request approval or revise the charter")
        return AuthorityDecision(
            AuthorityOutcome.ALLOWED_WITHIN_LIMIT.value if action.cost or action.workspace else AuthorityOutcome.ALLOWED.value,
            "delegation-envelope",
            "authority_envelope",
            {"maximum_cost": charter.authority_envelope.maximum_cost, "risk_limit": charter.authority_envelope.risk_limit},
            "deterministic charter policy permits the action",
            "execute and preserve evidence",
        )

    def _constraint_error(
        self, charter: ProjectCharter, action: ProposedAction
    ) -> AuthorityDecision | None:
        envelope = charter.authority_envelope
        if action.spending or action.cost is None or (action.cost or 0) > 0:
            if action.cost is None:
                return self._decision(
                    AuthorityOutcome.DENIED,
                    "unknown-cost",
                    "cost",
                    "paid or potentially paid work requires a known cost",
                    "supply a trusted exact cost before approval",
                )
            if (
                charter.budget_limit <= 0
                or envelope.maximum_cost <= 0
                or envelope.currency is None
            ):
                return self._decision(
                    AuthorityOutcome.DENIED,
                    "absent-spending-authority",
                    "budget_policy",
                    "delegation does not itself grant spending authority",
                    "obtain explicit Founder spending authority",
                )
            if action.currency != envelope.currency:
                return self._decision(
                    AuthorityOutcome.DENIED,
                    "currency-mismatch",
                    "authority_envelope.currency",
                    "implicit currency conversion is not permitted",
                    "use the approved canonical currency",
                )
        if (action.cost or 0) > min(charter.budget_limit, envelope.maximum_cost):
            return self._decision(AuthorityOutcome.DENIED, "budget-limit", "budget_limit", "action cost exceeds the approved budget", "reduce cost or revise the charter")
        if action.provider and (
            action.provider in charter.prohibited_providers
            or action.provider not in charter.approved_providers
            or action.provider not in envelope.allowed_providers
        ):
            return self._decision(AuthorityOutcome.DENIED, "provider-allowlist", "approved_providers", "provider is not approved", "select an approved provider")
        if action.tool and (
            action.tool in charter.prohibited_tools
            or action.tool not in charter.approved_tools
            or action.tool not in envelope.allowed_tools
        ):
            return self._decision(AuthorityOutcome.DENIED, "tool-allowlist", "approved_tools", "tool is not approved", "select an approved tool")
        if action.workspace:
            try:
                target = Path(action.workspace).resolve()
                roots = tuple(Path(item).resolve() for item in envelope.allowed_workspaces)
            except OSError:
                return self._decision(AuthorityOutcome.INDETERMINATE, "workspace-canonicalization", "workspaces", "workspace cannot be canonicalized", "pause and verify the workspace")
            if not any(target == root or target.is_relative_to(root) for root in roots):
                return self._decision(AuthorityOutcome.DENIED, "workspace-containment", "workspaces", "workspace is outside approved roots", "use an approved workspace")
        if action.data_classification not in envelope.data_classifications:
            return self._decision(AuthorityOutcome.DENIED, "data-classification", "data_privacy_restrictions", "data classification is not approved", "revise data authority")
        return None

    def _classification_error(
        self, action: ProposedAction
    ) -> AuthorityDecision | None:
        category = ActionCategory(action.category)
        text = _normalized(
            " ".join((action.objective, action.target_resource, *action.scope))
        )
        required: ActionCategory | None = None
        if action.deployment or _contains_any(
            text, ("production deployment", "deploy production", "deploy to production")
        ):
            required = ActionCategory.DEPLOY_PRODUCTION
        elif action.publication or _contains_any(
            text, ("publish externally", "external publication", "public release")
        ):
            required = ActionCategory.PUBLISH_EXTERNAL
        elif action.spending or _contains_any(
            text, ("purchase", "paid provider", "spend money", "buy ")
        ):
            required = (
                ActionCategory.PURCHASE
                if "purchase" in text or "buy " in text
                else ActionCategory.SPEND
            )
        elif action.git_mutation == "REWRITE_HISTORY" or _contains_any(
            text, ("rewrite history", "force push", "reset --hard")
        ):
            required = ActionCategory.REWRITE_HISTORY
        elif action.security_boundary_impact or _contains_any(
            text, ("change security boundary", "disable authentication")
        ):
            required = ActionCategory.CHANGE_SECURITY_BOUNDARY
        elif _contains_any(text, ("enable live trading", "place live trade")):
            required = ActionCategory.ENABLE_LIVE_TRADING
        if required is not None and category is not required:
            return self._decision(
                AuthorityOutcome.DENIED,
                "classification-mismatch",
                "category",
                f"trusted action facts require {required.value}, not {category.value}",
                "correct the durable workflow classification",
            )
        return None

    def _matching_approval(
        self,
        charter: ProjectCharter,
        action: ProposedAction,
        approvals: tuple[ApprovalRecord, ...],
        now: datetime,
    ) -> ApprovalRecord | str | None:
        expired = False
        revoked = False
        for approval in approvals:
            if (
                approval.project_id != charter.project_id
                or approval.charter_id != charter.charter_id
                or approval.charter_revision != charter.revision
                or approval.action_category not in {None, action.category}
                or not set(action.scope).issubset(set(approval.scope))
            ):
                continue
            if approval.revoked_at is not None:
                revoked = True
                continue
            if approval.expires_at is not None and datetime.fromisoformat(approval.expires_at) <= now:
                expired = True
                continue
            if approval.kind == ApprovalKind.ONE_TIME and approval.consumed_at is not None:
                continue
            amount = approval.limits.get("maximum_cost")
            if isinstance(amount, (int, float)) and (
                action.cost is None or action.cost > float(amount)
            ):
                continue
            provider = approval.limits.get("provider")
            if provider is not None and action.provider != provider:
                continue
            workspace = approval.limits.get("workspace")
            if workspace is not None and action.workspace != workspace:
                continue
            return approval
        if revoked:
            return "REVOKED"
        if expired:
            return "EXPIRED"
        return None

    @staticmethod
    def _decision(
        outcome: AuthorityOutcome,
        rule: str,
        field: str,
        reason: str,
        next_step: str,
    ) -> AuthorityDecision:
        return AuthorityDecision(outcome.value, rule, field, {}, reason, next_step)


class TrustedActionClassifier:
    """Derive launch facts from the durable task and charter, never caller labels."""

    def classify(
        self,
        task: ExecutiveTask,
        charter: ProjectCharter,
        specialist: SpecialistProfile,
    ) -> ProposedAction:
        if task.project_id != charter.project_id or task.charter_id != charter.charter_id:
            raise PermissionError("task and charter identity do not match")
        if len(charter.workspaces) != 1 or len(charter.approved_tools) != 1:
            raise PermissionError(
                "workflow launch requires one explicit workspace and tool"
            )
        if not charter.authority_envelope.data_classifications:
            raise PermissionError("workflow data classification is missing")
        text = _normalized(
            " ".join((task.title, task.objective, *task.instructions))
        )
        deployment = _contains_any(
            text, ("production deployment", "deploy production", "deploy to production")
        )
        publication = _contains_any(
            text, ("publish externally", "external publication", "public release")
        )
        spending = _contains_any(
            text, ("purchase", "paid provider", "spend money", "buy ")
        )
        git_mutation = (
            "REWRITE_HISTORY"
            if _contains_any(text, ("rewrite history", "force push", "reset --hard"))
            else ("MUTATE" if "commit" in text or "push" in text else None)
        )
        security_impact = _contains_any(
            text, ("change security boundary", "disable authentication")
        )
        action = ProposedAction(
            action_id=f"task-action:{task.task_id}",
            project_id=task.project_id,
            charter_revision=task.charter_revision,
            category=task.authority_category,
            target_resource=task.objective,
            provider=specialist.provider_id,
            tool=charter.approved_tools[0],
            workspace=charter.workspaces[0],
            scope=charter.deliverables,
            cost=0.0,
            reversible=not (
                deployment
                or publication
                or spending
                or git_mutation == "REWRITE_HISTORY"
            ),
            risk=charter.risk_classification,
            data_classification=charter.authority_envelope.data_classifications[0],
            external_side_effect=deployment
            or publication
            or spending
            or git_mutation is not None,
            objective=task.objective,
            currency=charter.authority_envelope.currency,
            publication=publication,
            deployment=deployment,
            spending=spending,
            git_mutation=git_mutation,
            security_boundary_impact=security_impact,
            trusted_source="DURABLE_WORKFLOW_TASK",
        )
        mismatch = AuthorityEvaluator()._classification_error(action)
        if mismatch is not None:
            raise PermissionError(mismatch.reason)
        return action


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9/ ._-]+", " ", value.casefold())).strip()


def _contains_any(value: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in value for phrase in phrases)


def _action_matches_non_goal(action: ProposedAction, non_goal: str) -> bool:
    denied = _normalized(non_goal)
    if not denied:
        return False
    material = _normalized(
        " ".join(
            (
                action.objective,
                action.target_resource,
                action.category,
                *action.scope,
            )
        )
    )
    if denied in material:
        return True
    denied_tokens = {
        token
        for token in denied.split()
        if len(token) > 3 and token not in {"with", "from", "that", "this"}
    }
    material_tokens = set(material.split())
    return bool(denied_tokens) and denied_tokens.issubset(material_tokens)
