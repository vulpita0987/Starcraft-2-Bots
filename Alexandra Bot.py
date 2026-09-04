from sc2 import maps
from sc2.bot_ai import BotAI
from sc2.data import Difficulty, Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.main import run_game
from sc2.player import Bot, Computer


class ThreebaseVoidrayBot(BotAI):
    async def on_start(self):
        # Compatibility for SC2 build 97563's missing Probe gather ability.
        if 4135 not in self.game_data.abilities:
            gather = self.game_data.abilities.get(AbilityId.HARVEST_GATHER.value)
            if gather is not None:
                self.game_data.abilities[4135] = gather

    async def on_step(self, iteration: int):
        stargate_start_base_count = 2
        max_base_count = 3
        target_stargate_count = 2
        third_base_after_voidrays = 4
        split_voidray_count = 10

        if iteration == 0:
            await self.chat_send("(glhf)")

        if not self.townhalls.ready:
            for worker in self.workers:
                worker.attack(self.enemy_start_locations[0])
            return

        nexus = self.townhalls.ready.random
        voidrays = self.units(UnitTypeId.VOIDRAY)
        enemy_main = self.enemy_start_locations[0]

        if not nexus.is_idle and not nexus.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
            nexuses = self.structures(UnitTypeId.NEXUS)
            abilities = await self.get_available_abilities(nexuses)
            for loop_nexus, abilities_nexus in zip(nexuses, abilities):
                if AbilityId.EFFECT_CHRONOBOOSTENERGYCOST in abilities_nexus:
                    loop_nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, nexus)
                    break

        if voidrays.amount >= split_voidray_count:
            self.manage_voidray_groups(voidrays, enemy_main)
        elif voidrays:
            threats = (self.enemy_units | self.enemy_structures).filter(
                lambda unit: unit.can_be_attacked
                and any(unit.distance_to(base) < 35 for base in self.townhalls.ready)
            )
            for vr in voidrays:
                vr.attack(threats.closest_to(vr) if threats else nexus.position)

        # Give ready Stargates first use of resources so Void Rays are constant.
        for stargate in self.structures(UnitTypeId.STARGATE).ready.idle:
            if self.can_afford(UnitTypeId.VOIDRAY):
                stargate.train(UnitTypeId.VOIDRAY)

        await self.distribute_workers()

        if (
            self.supply_left < 2
            and self.already_pending(UnitTypeId.PYLON) == 0
            or self.supply_used > 15
            and self.supply_left < 4
            and self.already_pending(UnitTypeId.PYLON) < 2
        ):
            if self.can_afford(UnitTypeId.PYLON):
                await self.build(UnitTypeId.PYLON, near=nexus)

        if self.structures(UnitTypeId.PYLON).ready:
            pylon = self.structures(UnitTypeId.PYLON).ready.random
            if self.structures(UnitTypeId.GATEWAY).ready:
                if (
                    not self.structures(UnitTypeId.CYBERNETICSCORE)
                    and self.can_afford(UnitTypeId.CYBERNETICSCORE)
                    and self.already_pending(UnitTypeId.CYBERNETICSCORE) == 0
                ):
                    await self.build(UnitTypeId.CYBERNETICSCORE, near=pylon)
            elif (
                self.can_afford(UnitTypeId.GATEWAY)
                and self.already_pending(UnitTypeId.GATEWAY) == 0
            ):
                await self.build(UnitTypeId.GATEWAY, near=pylon)

        if self.structures(UnitTypeId.CYBERNETICSCORE):
            for base in self.townhalls.ready:
                for geyser in self.vespene_geyser.closer_than(15, base):
                    if self.can_afford(UnitTypeId.ASSIMILATOR):
                        worker = self.select_build_worker(geyser.position)
                        if worker and not self.gas_buildings.closer_than(1, geyser):
                            worker.build_gas(geyser)
                            worker.stop(queue=True)

        base_count = self.townhalls.ready.amount + self.already_pending(UnitTypeId.NEXUS)
        if (
            base_count < stargate_start_base_count
            and self.can_afford(UnitTypeId.NEXUS)
        ):
            await self.expand_now()
        elif (
            base_count < max_base_count
            and voidrays.amount >= third_base_after_voidrays
            and self.can_afford(UnitTypeId.NEXUS)
        ):
            await self.expand_now()

        stargate_count = (
            self.structures(UnitTypeId.STARGATE).ready.amount
            + self.already_pending(UnitTypeId.STARGATE)
        )
        if (
            base_count >= stargate_start_base_count
            and stargate_count < target_stargate_count
            and self.structures(UnitTypeId.CYBERNETICSCORE).ready
        ):
            for base in self.townhalls:
                if self.structures(UnitTypeId.STARGATE).closer_than(20, base):
                    continue
                pylons = self.structures(UnitTypeId.PYLON).ready.closer_than(18, base)
                if pylons and self.can_afford(UnitTypeId.STARGATE):
                    await self.build(UnitTypeId.STARGATE, near=pylons.closest_to(base))
                elif not pylons and self.already_pending(UnitTypeId.PYLON) == 0:
                    if self.can_afford(UnitTypeId.PYLON):
                        await self.build(UnitTypeId.PYLON, near=base)
                break

        if (
            self.supply_workers + self.already_pending(UnitTypeId.PROBE)
            < self.townhalls.amount * 22
            and nexus.is_idle
            and self.can_afford(UnitTypeId.PROBE)
        ):
            nexus.train(UnitTypeId.PROBE)

    def manage_voidray_groups(self, voidrays, enemy_main):
        """Keep five stable defenders and send every other Void Ray to attack."""
        bases = sorted(
            self.townhalls.ready,
            key=lambda base: base.distance_to(self.start_location),
        )

        if not hasattr(self, "voidray_defender_tags"):
            self.voidray_defender_tags = set()

        living_tags = {voidray.tag for voidray in voidrays}
        self.voidray_defender_tags.intersection_update(living_tags)
        defenders_needed = 5 - len(self.voidray_defender_tags)
        if defenders_needed > 0:
            replacements = sorted(
                (
                    voidray
                    for voidray in voidrays
                    if voidray.tag not in self.voidray_defender_tags
                ),
                key=lambda voidray: min(voidray.distance_to(base) for base in bases),
            )
            self.voidray_defender_tags.update(
                voidray.tag for voidray in replacements[:defenders_needed]
            )

        defenders = [
            voidray
            for voidray in voidrays
            if voidray.tag in self.voidray_defender_tags
        ]
        attackers = [
            voidray
            for voidray in voidrays
            if voidray.tag not in self.voidray_defender_tags
        ]
        threats = (self.enemy_units | self.enemy_structures).filter(
            lambda unit: unit.can_be_attacked
            and any(unit.distance_to(base) < 35 for base in bases)
        )

        for index, defender in enumerate(defenders):
            if threats:
                defender.attack(threats.closest_to(defender))
            else:
                defender.attack(bases[index % len(bases)].position)

        if not attackers:
            return

        if not hasattr(self, "search_points"):
            enemy_base_sites = sorted(
                (
                    point
                    for point in self.expansion_locations_list
                    if point.distance_to(enemy_main) > 5
                ),
                key=lambda point: point.distance_to(enemy_main),
            )
            self.search_points = [enemy_main, *enemy_base_sites]
            self.sweep_index = 0

        search_target = self.search_points[self.sweep_index]
        enemy_bases_at_target = self.enemy_structures.filter(
            lambda unit: unit.can_be_attacked
            and unit.distance_to(search_target) < 22
        )
        if (
            any(voidray.distance_to(search_target) < 12 for voidray in attackers)
            and not enemy_bases_at_target
        ):
            for _ in self.search_points:
                self.sweep_index = (self.sweep_index + 1) % len(self.search_points)
                search_target = self.search_points[self.sweep_index]
                if not self.townhalls.ready.closer_than(15, search_target):
                    break

        for voidray in attackers:
            if voidray.weapon_cooldown > 0:
                voidray(AbilityId.EFFECT_VOIDRAYPRISMATICALIGNMENT)
            voidray.attack(search_target)


# Required by run_match.py and run_match.bat.
SimpleProtossBot = ThreebaseVoidrayBot


def main():
    run_game(
        maps.get("(2)CatalystLE"),
        [
            Bot(Race.Protoss, ThreebaseVoidrayBot()),
            Computer(Race.Protoss, Difficulty.Easy),
        ],
        realtime=False,
    )


if __name__ == "__main__":
    main()