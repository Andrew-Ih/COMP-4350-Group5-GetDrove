"""Application use cases for a driver's auto-accept rules (#42)."""

from uuid import UUID

from trips.application.ports import AutoAcceptRulesRepository
from trips.domain.auto_accept import AutoAcceptRules


class GetAutoAcceptRules:
    """GET /auto-accept: the driver's rules, or the defaults if they've never set any."""

    def __init__(self, repository: AutoAcceptRulesRepository) -> None:
        self.repository = repository

    async def execute(self, driver_id: UUID) -> AutoAcceptRules:
        return await self.repository.get(driver_id) or AutoAcceptRules()


class SetAutoAcceptRules:
    """PUT /auto-accept: saves the driver's rules. They apply to requests made from now on;
    requests already waiting aren't looked at again."""

    def __init__(self, repository: AutoAcceptRulesRepository) -> None:
        self.repository = repository

    async def execute(self, driver_id: UUID, rules: AutoAcceptRules) -> AutoAcceptRules:
        await self.repository.save(driver_id, rules)
        return rules
