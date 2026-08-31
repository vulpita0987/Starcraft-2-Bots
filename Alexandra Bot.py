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
            gather = self.game_data.abilities.get(
                AbilityId.HARVEST_GATHER.value
            )
            if gather is not None:
                self.game_data.abilities[4135] = gather

    async def on_step(self, iteration: int):
        target_base_count = 2
        target_stargate_count = 2

        if iteration == 0:
            await self.chat_send("(glhf)")

        if not self.townhalls.ready:
            for worker in self.workers:
                worker.attack(self.enemy_start_locations[0])
            return

        nexus = self.townhalls.ready.random

        # Chronoboost busy Nexuses.
        if (
            not nexus.is_idle
            and not nexus.has_buff(BuffId.CHRONOBOOSTENERGYCOST)
        ):
            nexuses = self.structures(UnitTypeId.NEXUS)
            abilities = await self.get_available_abilities(nexuses)

            for loop_nexus, nexus_abilities in zip(nexuses, abilities):
                if (
                    AbilityId.EFFECT_CHRONOBOOSTENERGYCOST
                    in nexus_abilities
                ):
                    loop_nexus(
                        AbilityId.EFFECT_CHRONOBOOSTENERGYCOST,
                        nexus,
                    )
                    break

        voidrays = self.units(UnitTypeId.VOIDRAY)
        enemy_main = self.enemy_start_locations[0]

        if not hasattr(self, "enemy_main_destroyed"):
            self.enemy_main_destroyed = False

        if (
            self.is_visible(enemy_main)
            and not self.enemy_structures.closer_than(
                20,
                enemy_main,
            ).exists
        ):
            self.enemy_main_destroyed = True

        # With more than 15 Void Rays, keep five at home.
        if voidrays.amount > 15:
            self.manage_large_voidray_force(voidrays)

        # Normal attack logic for 6–15 Void Rays.
        elif voidrays.amount > 5:
            if self.enemy_main_destroyed:
                if not hasattr(self, "sweep_index"):
                    self.sweep_index = 0

                sweep_locations = list(
                    self.expansion_locations_list
                )

                if sweep_locations:
                    sweep_target = sweep_locations[
                        self.sweep_index
                    ]

                    if all(
                        voidray.distance_to(sweep_target) < 10
                        for voidray in voidrays
                    ):
                        self.sweep_index = (
                            self.sweep_index + 1
                        ) % len(sweep_locations)

                        sweep_target = sweep_locations[
                            self.sweep_index
                        ]

                    for voidray in voidrays:
                        voidray.attack(sweep_target)

            else:
                for voidray in voidrays:
                    if voidray.weapon_cooldown > 0:
                        voidray(
                            AbilityId
                            .EFFECT_VOIDRAYPRISMATICALIGNMENT
                        )

                    targets = (
                        self.enemy_units
                        | self.enemy_structures
                    ).filter(
                        lambda enemy: enemy.can_be_attacked
                    )

                    if targets:
                        voidray.attack(
                            targets.closest_to(voidray)
                        )
                    else:
                        voidray.attack(enemy_main)

        # Void Rays get first spending priority.
        for stargate in self.structures(
            UnitTypeId.STARGATE
        ).ready.idle:
            if self.can_afford(UnitTypeId.VOIDRAY):
                stargate.train(UnitTypeId.VOIDRAY)

        await self.distribute_workers()

        # Build Pylons when supply is getting low.
        if (
            (
                self.supply_left < 2
                and self.already_pending(
                    UnitTypeId.PYLON
                ) == 0
            )
            or (
                self.supply_used > 15
                and self.supply_left < 4
                and self.already_pending(
                    UnitTypeId.PYLON
                ) < 2
            )
        ):
            if self.can_afford(UnitTypeId.PYLON):
                await self.build(
                    UnitTypeId.PYLON,
                    near=nexus,
                )

        # Train Probes until each Nexus has about 22.
        if (
            self.supply_workers
            + self.already_pending(UnitTypeId.PROBE)
            < self.townhalls.amount * 22
            and nexus.is_idle
        ):
            if self.can_afford(UnitTypeId.PROBE):
                nexus.train(UnitTypeId.PROBE)

        # Build Gateway followed by Cybernetics Core.
        if self.structures(UnitTypeId.PYLON).ready:
            pylon = self.structures(
                UnitTypeId.PYLON
            ).ready.random

            if self.structures(UnitTypeId.GATEWAY).ready:
                if not self.structures(
                    UnitTypeId.CYBERNETICSCORE
                ):
                    if (
                        self.can_afford(
                            UnitTypeId.CYBERNETICSCORE
                        )
                        and self.already_pending(
                            UnitTypeId.CYBERNETICSCORE
                        ) == 0
                    ):
                        await self.build(
                            UnitTypeId.CYBERNETICSCORE,
                            near=pylon,
                        )
            else:
                if (
                    self.can_afford(UnitTypeId.GATEWAY)
                    and self.already_pending(
                        UnitTypeId.GATEWAY
                    ) == 0
                ):
                    await self.build(
                        UnitTypeId.GATEWAY,
                        near=pylon,
                    )

        # Build Assimilators at completed Nexuses.
        if self.structures(UnitTypeId.CYBERNETICSCORE):
            for base in self.townhalls.ready:
                geysers = self.vespene_geyser.closer_than(
                    15,
                    base,
                )

                for geyser in geysers:
                    if self.can_afford(
                        UnitTypeId.ASSIMILATOR
                    ):
                        worker = self.select_build_worker(
                            geyser.position
                        )

                        if worker is not None:
                            has_assimilator = (
                                self.gas_buildings
                                and self.gas_buildings
                                .closer_than(1, geyser)
                            )

                            if not has_assimilator:
                                worker.build_gas(geyser)
                                worker.stop(queue=True)

        # Build two Stargates once the second Nexus is
        # started or completed.
        if (
            self.structures(UnitTypeId.PYLON).ready
            and self.structures(
                UnitTypeId.CYBERNETICSCORE
            ).ready
        ):
            pylon = self.structures(
                UnitTypeId.PYLON
            ).ready.random

            base_total = (
                self.townhalls.ready.amount
                + self.already_pending(UnitTypeId.NEXUS)
            )

            stargate_total = (
                self.structures(
                    UnitTypeId.STARGATE
                ).ready.amount
                + self.already_pending(
                    UnitTypeId.STARGATE
                )
            )

            if (
                base_total >= target_base_count
                and stargate_total
                < target_stargate_count
                and self.can_afford(
                    UnitTypeId.STARGATE
                )
            ):
                await self.build(
                    UnitTypeId.STARGATE,
                    near=pylon,
                )

        # Reach two bases first. Do not build the third
        # Nexus until the first Void Ray is complete.
        current_and_pending_bases = (
            self.townhalls.ready.amount
            + self.already_pending(UnitTypeId.NEXUS)
        )

        if (
            current_and_pending_bases
            < target_base_count
        ):
            if self.can_afford(UnitTypeId.NEXUS):
                await self.expand_now()

        elif (
            voidrays.exists
            and current_and_pending_bases < 3
        ):
            if self.can_afford(UnitTypeId.NEXUS):
                await self.expand_now()

    def manage_large_voidray_force(self, voidrays):
        """
        Keep five Void Rays at home and attack-move
        every other Void Ray through the base sites.
        """
        defense_base = self.townhalls.ready.closest_to(
            self.start_location
        )
        defense_point = defense_base.position

        if not hasattr(self, "voidray_defender_tags"):
            self.voidray_defender_tags = set()

        living_tags = {
            voidray.tag for voidray in voidrays
        }

        self.voidray_defender_tags.intersection_update(
            living_tags
        )

        defenders_needed = (
            5 - len(self.voidray_defender_tags)
        )

        if defenders_needed > 0:
            available_voidrays = sorted(
                (
                    voidray
                    for voidray in voidrays
                    if voidray.tag
                    not in self.voidray_defender_tags
                ),
                key=lambda voidray: voidray.distance_to(
                    defense_point
                ),
            )

            self.voidray_defender_tags.update(
                voidray.tag
                for voidray in available_voidrays[
                    :defenders_needed
                ]
            )

        defenders = [
            voidray
            for voidray in voidrays
            if voidray.tag
            in self.voidray_defender_tags
        ]

        attackers = [
            voidray
            for voidray in voidrays
            if voidray.tag
            not in self.voidray_defender_tags
        ]

        visible_threats = (
            self.enemy_units | self.enemy_structures
        ).filter(
            lambda enemy: (
                enemy.can_be_attacked
                and enemy.distance_to(defense_point) < 35
            )
        )

        # Five defenders remain at home and attack
        # visible nearby enemies.
        for defender in defenders:
            if visible_threats:
                defender.attack(
                    visible_threats.closest_to(defender)
                )
            else:
                defender.attack(defense_point)

        # All other Void Rays attack-move through every
        # possible base location.
        base_sites = sorted(
            self.expansion_locations_list,
            key=lambda location: location.distance_to(
                self.enemy_start_locations[0]
            ),
        )

        if not attackers or not base_sites:
            return

        if not hasattr(
            self,
            "large_force_sweep_index",
        ):
            self.large_force_sweep_index = 0
            self.large_force_order_index = {}

        target = base_sites[
            self.large_force_sweep_index
        ]

        if all(
            attacker.distance_to(target) < 10
            for attacker in attackers
        ):
            self.large_force_sweep_index = (
                self.large_force_sweep_index + 1
            ) % len(base_sites)

            target = base_sites[
                self.large_force_sweep_index
            ]

        for attacker in attackers:
            old_target_index = (
                self.large_force_order_index.get(
                    attacker.tag
                )
            )

            if (
                old_target_index
                != self.large_force_sweep_index
            ):
                attacker.attack(target)

                self.large_force_order_index[
                    attacker.tag
                ] = self.large_force_sweep_index


# Required by run_match.py and run_match.bat.
SimpleProtossBot = ThreebaseVoidrayBot


def main():
    run_game(
        maps.get("(2)CatalystLE"),
        [
            Bot(
                Race.Protoss,
                ThreebaseVoidrayBot(),
            ),
            Computer(
                Race.Protoss,
                Difficulty.Easy,
            ),
        ],
        realtime=False,
    )


if __name__ == "__main__":
    main()