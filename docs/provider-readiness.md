# Model provider readiness (Stage 2)

## Current governed path

Agents carry only `model_policy_ref`. `GovernedModelGateway` authorizes that reference with
`ModelPolicy`, checks the execution budget with `BudgetGuard`, and asks `ModelRouter` for the
configured `ProviderAdapter`. `StaticModelRouter` maps `policy_ref -> route_id -> adapter`.
Agents, domain code, and runtime code do not select a provider or model.

The deployment default is `DEFAULT_MODEL_ROUTE=disabled`. The only production adapter currently
present is `DisabledProviderAdapter`; normal runtime therefore fails closed with
`MODEL_ROUTE_NOT_CONFIGURED`. The `deterministic.integration` route exists only inside the explicit
TEST runtime and reports zero estimated model cost.

## Configuration ownership

Provider selection, model name, and credentials must be deployment-managed. Credentials must be
injected by the deployment secret mechanism and consumed only by an adapter under
`genesis.adapters.providers`. They must not appear in an AgentDefinition, prompt, repository file,
or direct agent/runtime SDK import.

## PROVIDER_FOLLOWUP

Real-provider activation is intentionally not part of Stage 2 because the current deployment has
no authoritative policy-route manifest, provider/model configuration, credential secret contract,
or staging egress configuration.

- `genesis-ai` (blocking real-provider proof): add one adapter behind `ModelProviderAdapter`, typed
  provider settings, usage/cost normalization, timeout/retry behavior, and composition of the
  governed gateway from deployment configuration.
- `alos-infra` (blocking real-provider proof): define the policy-route manifest, secret name/mount,
  staging-only enablement, network egress, rotation, and rollback procedure.
- `alos-backend` (non-blocking deterministic proof): decide whether policy references remain solely
  in canonical AgentDefinition or are additionally validated against a Backend-owned policy
  registry before activation.

Until those controls exist, no provider SDK, secret, production route, or model name should be
hardcoded into GENESIS.
