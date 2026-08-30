from sc2 import maps
from sc2.bot_ai import BotAI
from sc2.data import Difficulty, Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as U
from sc2.main import run_game
from sc2.player import Bot, Computer


class SimpleProtossBot(BotAI):
    # ---------- SETTINGS ----------
    TARGET_BASES = 5
    WORKERS_PER_BASE = 22
    TARGET_STARGATES = 6

    async def on_step(self, iteration: int):
        # Do not throw Probes away if all Nexuses are destroyed.
        if not self.townhalls.ready.exists:
            return

        await self.manage_workers()
        await self.manage_pylons()
        await self.manage_expansions()
        await self.manage_tech()
        await self.manage_gas()
        await self.manage_voidray_production()
        await self.manage_voidray_attacks()

    # ---------- WORKERS ----------
    async def manage_workers(self):
        worker_cap = self.TARGET_BASES * self.WORKERS_PER_BASE

        # Build Probes up to 22 per Nexus.
        if self.workers.amount < worker_cap and self.can_afford(U.PROBE):
            for nexus in self.townhalls.ready.idle:
                nexus.train(U.PROBE)
                break

        # Send idle Probes to gas first, then minerals.
        # The try avoids the old ability 4135 worker-order error.
        try:
            idle_workers = self.workers.idle
        except KeyError:
            return

        for worker in idle_workers:
            gas_buildings = self.structures(U.ASSIMILATOR).ready.filter(
                lambda gas: gas.assigned_harvesters < gas.ideal_harvesters
            )

            if gas_buildings.exists:
                worker.gather(gas_buildings.closest_to(worker))
                continue

            minerals = self.mineral_field.closer_than(12, worker.position)

            if minerals.exists:
                worker.gather(minerals.closest_to(worker))

    # ---------- PYLONS ----------
    async def manage_pylons(self):
        supply_needed = 2 if self.supply_used < 30 else 4

        if (
            self.supply_left < supply_needed
            and self.already_pending(U.PYLON) == 0
            and self.can_afford(U.PYLON)
            and self.workers.exists
        ):
            nexus = self.townhalls.ready.first
            worker = self.workers.closest_to(nexus)

            await self.build(
                U.PYLON,
                near=nexus,
                build_worker=worker,
            )

    # ---------- EXPANSIONS ----------
    async def manage_expansions(self):
        base_total = (
            self.townhalls.ready.amount
            + self.already_pending(U.NEXUS)
        )

        # Build one Nexus at a time, normally at the nearest free expansion.
        # Wait for 16 workers per existing base before expanding again.
        worker_requirement = self.townhalls.ready.amount * 16

        if (
            base_total >= self.TARGET_BASES
            or self.already_pending(U.NEXUS) > 0
            or self.workers.amount < worker_requirement
            or not self.can_afford(U.NEXUS)
            or not self.workers.exists
        ):
            return

        location = await self.get_next_expansion()

        if location is None:
            return

        worker = self.workers.closest_to(location)

        await self.build(
            U.NEXUS,
            near=location,
            build_worker=worker,
        )

    # ---------- BUILDINGS ----------
    async def manage_tech(self):
        pylons = self.structures(U.PYLON).ready

        if not pylons.exists or not self.workers.exists:
            return

        pylon = pylons.closest_to(self.townhalls.ready.first)

        # Gateway first.
        if not self.structures(U.GATEWAY).exists:
            await self.build_building(U.GATEWAY, pylon)
            return

        # Then Cybernetics Core.
        if not self.structures(U.CYBERNETICSCORE).exists:
            await self.build_building(U.CYBERNETICSCORE, pylon)
            return

        # Do not wait for two bases. Start Stargates as soon as the Core finishes.
        if not self.structures(U.CYBERNETICSCORE).ready.exists:
            return

        stargate_total = (
            self.structures(U.STARGATE).ready.amount
            + self.already_pending(U.STARGATE)
        )

        if stargate_total < self.TARGET_STARGATES:
            await self.build_building(U.STARGATE, pylon)

    async def build_building(self, building, near):
        if (
            self.already_pending(building) > 0
            or not self.can_afford(building)
            or not self.workers.exists
        ):
            return

        worker = self.workers.closest_to(near)

        await self.build(
            building,
            near=near,
            build_worker=worker,
        )

    # ---------- GAS ----------
    async def manage_gas(self):
        if not self.structures(U.CYBERNETICSCORE).exists:
            return

        # Build Assimilators only on the geysers beside each Nexus.
        for nexus in self.townhalls.ready:
            geysers = self.vespene_geyser.closer_than(15, nexus.position)

            for geyser in geysers:
                existing_assimilator = self.structures(U.ASSIMILATOR).closer_than(
                    1,
                    geyser.position,
                )

                if (
                    existing_assimilator.exists
                    or not self.can_afford(U.ASSIMILATOR)
                    or not self.workers.exists
                ):
                    continue

                # Avoid select_build_worker(), which caused the old error.
                worker = self.workers.closest_to(geyser.position)
                worker.build(U.ASSIMILATOR, geyser)

                # Only order one gas building per game step.
                return

    # ---------- VOID RAY PRODUCTION ----------
    async def manage_voidray_production(self):
        for stargate in self.structures(U.STARGATE).ready.idle:
            if self.can_afford(U.VOIDRAY):
                stargate.train(U.VOIDRAY)

    # ---------- VOID RAY ATTACKS ----------
    async def manage_voidray_attacks(self):
        voidrays = self.units(U.VOIDRAY)

        # Attack immediately when the first Void Ray exists.
        if not voidrays.exists:
            return

        enemy_main = self.enemy_start_locations[0]

        # Only start sweeping once the enemy main is visible and has no buildings.
        enemy_main_destroyed = (
            self.is_visible(enemy_main)
            and not self.enemy_structures.closer_than(20, enemy_main).exists
        )

        if enemy_main_destroyed:
            if not hasattr(self, "sweep_index"):
                self.sweep_index = 0

            sweep_target = self.expansion_locations_list[self.sweep_index]

            # Move the group to the next location after it reaches this one.
            if all(vr.distance_to(sweep_target) < 10 for vr in voidrays):
                self.sweep_index = (
                    self.sweep_index + 1
                ) % len(self.expansion_locations_list)

                sweep_target = self.expansion_locations_list[
                    self.sweep_index
                ]

            for vr in voidrays:
                # attack(point) is an attack-move order.
                vr.attack(sweep_target)

            return

        targets = (self.enemy_units | self.enemy_structures).filter(
            lambda unit: unit.can_be_attacked
        )

        for vr in voidrays:
            if vr.weapon_cooldown > 0:
                vr(AbilityId.EFFECT_VOIDRAYPRISMATICALIGNMENT)

            if targets.exists:
                vr.attack(targets.closest_to(vr))
            else:
                vr.attack(enemy_main)


if __name__ == "__main__":
    run_game(
        maps.get("AbyssalReefLE"),
        [
            Bot(Race.Protoss, SimpleProtossBot()),
            Computer(Race.Terran, Difficulty.Easy),
        ],
        realtime=True,
    )