#Core bot and run loop
from sc2.bot_ai import BotAI
from sc2.main import run_game

#Game setup
from sc2.data import Race, Difficulty
from sc2.player import Bot, Computer
from sc2 import maps
from pathlib import Path

#Units, structures, and abilities
from sc2.ids.unit_typeid import UnitTypeId as U
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.upgrade_id import UpgradeId

#Positioning & geometry
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

#Events and game state
from sc2.game_info import GameInfo
from sc2.game_state import GameState

import math

map_path = maps.get("AbyssalReefLE")


class SimpleProtossBot(BotAI):

   
    def __init__(self):
        super().__init__()
       
        
    # ------ Cannona
    async def build_choke_cannons(self):

    # Need a pylon first
     if not self.structures(U.PYLON).ready.exists:
        return

     choke = self.main_base_ramp.top_center

     pylon = self.structures(U.PYLON).ready.closest_to(choke)

    # Permanent cannon locations
     if not hasattr(self, "choke_cannon_positions"):

        self.choke_cannon_positions = [
            pylon.position.towards(choke, 4),
            pylon.position.towards(choke, 4) + Point2((2, 0)),
            pylon.position.towards(choke, 4) + Point2((-2, 0)),
            pylon.position.towards(choke, 4) + Point2((0, 2)),
            pylon.position.towards(choke, 4) + Point2((0, -2)),
        ]


     cannons = self.structures(U.PHOTONCANNON)


    # Replace missing cannons one at a time
     for pos in self.choke_cannon_positions:

        if cannons.closer_than(2, pos).exists:
            continue


        # Don't queue duplicates
        if self.already_pending(U.PHOTONCANNON):
            return


        if self.can_afford(U.PHOTONCANNON):

            await self.build(
                U.PHOTONCANNON,
                near=pos
            )

            return



    async def manage_carriers(self):

    # ----------------------------
    # Build carriers
    # ----------------------------
     if self.structures(U.STARGATE).ready.exists:
        for sg in self.structures(U.STARGATE).ready:
            if (
                sg.is_idle
                and self.can_afford(U.CARRIER)
                and self.supply_left >= 6
            ):
                sg.train(U.CARRIER)

     carriers = self.units(U.CARRIER)

     if not carriers:
        return

    # ------------------------------------
    # Expansion locations (same every game
    # for the current map)
    # ------------------------------------
     if not hasattr(self, "carrier_locations"):
        self.carrier_locations = list(self.expansion_locations_list)

    # ------------------------------------
    # Store an index for EACH carrier
    # ------------------------------------
     if not hasattr(self, "carrier_targets"):
        self.carrier_targets = {}

     for carrier in carriers:

        # Assign first destination when spawned
        if carrier.tag not in self.carrier_targets:
            self.carrier_targets[carrier.tag] = 0

        index = self.carrier_targets[carrier.tag]
        target_location = self.carrier_locations[index]

        # Enemy structures close to this expansion
        nearby = self.enemy_structures.closer_than(
            20,
            target_location
        )

        # Attack buildings if there are any
        if nearby.exists:

            target = nearby.closest_to(carrier)

            carrier.attack(target)

        else:

            # Fly to expansion
            if carrier.distance_to(target_location) > 8:
                carrier.attack(target_location)

            else:
                # Expansion cleared
                index += 1

                if index >= len(self.carrier_locations):
                    index = 0

                self.carrier_targets[carrier.tag] = index

    async def manage_zealots(self):

    # ----------------------------
    # Build zealots
    # ----------------------------

     if not self.structures(U.GATEWAY).ready.exists:
        return

     gateway = self.structures(U.GATEWAY).ready.first

     if (
        self.can_afford(U.ZEALOT)
        and gateway.is_idle
        and self.supply_left > 0
     ):
        gateway.train(U.ZEALOT)

    # ----------------------------
    # Control zealots
    # ----------------------------

     zealots = self.units(U.ZEALOT)

     if not zealots.exists:
        return

    # Main destination
     if self.enemy_structures.exists:
        main_target = self.enemy_structures.closest_to(zealots.center)
     else:
        main_target = self.enemy_start_locations[0]

     for zealot in zealots:

        # Look for nearby enemies first
        nearby_enemies = self.enemy_units.closer_than(8, zealot)

        if nearby_enemies.exists:
            target = nearby_enemies.closest_to(zealot)

            # Only issue a new order if needed
            if zealot.order_target != target.tag:
                zealot.attack(target)

        # Otherwise continue advancing
        elif zealot.is_idle:
            zealot.attack(main_target)



   

    async def build_pylons(self):
     if not self.townhalls.ready.exists:
        return

     if not self.can_afford(U.PYLON):
        return

    # Don't queue another while one is already being built
     if self.already_pending(U.PYLON):
        return

     nexus = self.townhalls.first
     pylons = self.structures(U.PYLON)

    # ======================================================
    # First pylon behind the choke
    # ======================================================
     if pylons.amount == 0:
        choke = self.main_base_ramp.top_center

        # 6 tiles inside your base from the choke
        pos = choke.towards(self.start_location, 6)

        if await self.can_place(U.PYLON, pos):
            await self.build(U.PYLON, near=pos)

        return

    # ======================================================
    # Build more pylons only when supply is getting low
    # ======================================================
     if self.supply_left >= 4:
        return

    # Don't spam pylons
     if self.already_pending(U.PYLON) >= 2:
        return

     base_structures = self.structures.closer_than(30, nexus.position)

     candidate_positions = []

     for structure in base_structures:

        # Push the pylon away from the Nexus so it stays around
        # the outside of the base.
        direction = (structure.position - nexus.position)

        if direction.length > 0:
            direction = direction.normalized
        else:
            continue

        candidate_positions.extend([
            structure.position + direction * 5,
            structure.position + direction * 7,
            structure.position + Point2((4, 4)),
            structure.position + Point2((-4, 4)),
            structure.position + Point2((4, -4)),
            structure.position + Point2((-4, -4)),
        ])

     for pos in candidate_positions:

        # Keep pylons spread out
        if pylons.closer_than(8, pos).exists:
            continue

        if await self.can_place(U.PYLON, pos):
            await self.build(U.PYLON, near=pos)
            return

    async def manage_workers(self):

     if not self.townhalls.ready.exists:
        return

     nexus = self.townhalls.ready.first


    # ---------------------------------------------
    # Worker target:
    # 16 mineral workers + 6 gas workers
    # ---------------------------------------------

     worker_target = 22


     if (
        self.workers.amount < worker_target
        and self.can_afford(U.PROBE)
        and self.supply_left > 0
        and nexus.is_idle
     ):
        nexus.train(U.PROBE)


    # ---------------------------------------------
    # Protect expansion worker if one exists
    # ---------------------------------------------

     workers = self.workers

     if hasattr(self, "expansion_probe"):

        workers = workers.filter(
            lambda w: w.tag != self.expansion_probe
        )


    # ---------------------------------------------
    # Gas: exactly 3 per Assimilator
    # ---------------------------------------------

     for assimilator in self.structures(U.ASSIMILATOR).ready:

        assigned = assimilator.assigned_harvesters

        if assigned >= 3:
            continue


        needed = 3 - assigned


        for worker in workers.sorted_by_distance_to(assimilator):

            if needed <= 0:
                break


            if worker.is_gathering:
                continue


            worker.gather(assimilator)

            needed -= 1


    # ---------------------------------------------
    # Minerals
    # ---------------------------------------------

     minerals = self.mineral_field.closer_than(
        20,
        nexus
     )


     for worker in workers.idle:

        if minerals.exists:

            worker.gather(
                minerals.closest_to(worker)
            )

    async def manage_buildings(self):

     if not self.townhalls.ready.exists:
        return


     nexus = self.townhalls.ready.first

     center = self.game_info.map_center


     forge_pos = nexus.position.towards(center, 6)
     gateway_pos = nexus.position.towards(center, 10)
     cyber_pos = nexus.position.towards(center, 14)
     stargate_pos = nexus.position.towards(center, 18)
     fleet_pos = nexus.position.towards(center, 22)



    # ==============================
    # Forge
    # ==============================

     if (
        not self.structures(U.FORGE).exists
        and not self.already_pending(U.FORGE)
     ):

        if self.can_afford(U.FORGE):

            await self.build(
                U.FORGE,
                near=forge_pos
            )

        return



    # ==============================
    # Gateway
    # ==============================

     if (
        not self.structures(U.GATEWAY).exists
        and not self.already_pending(U.GATEWAY)
     ):

        if self.can_afford(U.GATEWAY):

            await self.build(
                U.GATEWAY,
                near=gateway_pos
            )

        return



    # ==============================
    # Cyber Core
    # ==============================

     if (
        self.structures(U.GATEWAY).ready.exists
        and not self.structures(U.CYBERNETICSCORE).exists
        and not self.already_pending(U.CYBERNETICSCORE)
     ):

        if self.can_afford(U.CYBERNETICSCORE):

            await self.build(
                U.CYBERNETICSCORE,
                near=cyber_pos
            )

        return



    # ==============================
    # Stargate
    # ==============================

     if (
        self.structures(U.CYBERNETICSCORE).ready.exists
        and not self.structures(U.STARGATE).exists
        and not self.already_pending(U.STARGATE)
     ):

        if self.can_afford(U.STARGATE):

            await self.build(
                U.STARGATE,
                near=stargate_pos
            )

        return



    # ==============================
    # Fleet Beacon
    # ==============================

     if (
        self.structures(U.STARGATE).ready.exists
        and not self.structures(U.FLEETBEACON).exists
        and not self.already_pending(U.FLEETBEACON)
     ):

        if self.can_afford(U.FLEETBEACON):

            await self.build(
                U.FLEETBEACON,
                near=fleet_pos
            )

    async def develop_expansions(self):

     for nexus in self.townhalls.ready:

        # Skip the starting base
        if nexus == self.townhalls.first:
            continue

        center = nexus.position.towards(
            self.game_info.map_center,
            6
        )

        # =====================================================
        # Build Assimilators
        # =====================================================

        geysers = self.vespene_geyser.closer_than(12, nexus)

        for geyser in geysers:

            if not self.structures(U.ASSIMILATOR).closer_than(1, geyser).exists:

                if self.can_afford(U.ASSIMILATOR):

                    worker = self.workers.closest_to(geyser)

                    if worker:
                        worker.build(U.ASSIMILATOR, geyser)

        # =====================================================
        # Build one Pylon
        # =====================================================

        pylons = self.structures(U.PYLON).closer_than(10, nexus)

        if pylons.amount == 0:

            if self.can_afford(U.PYLON):

                await self.build(
                    U.PYLON,
                    near=center
                )

            continue

        if not pylons.ready.exists:
            continue

        # =====================================================
        # Build two Stargates
        # =====================================================

        stargates = self.structures(U.STARGATE).closer_than(15, nexus)

        if stargates.amount < 2:

            if self.can_afford(U.STARGATE):

                pos = center.towards(
                    self.game_info.map_center,
                    5 + stargates.amount * 5
                )

                await self.build(
                    U.STARGATE,
                    near=pos
                )

            continue

        # =====================================================
        # Build one Shield Battery
        # =====================================================

        batteries = self.structures(U.SHIELDBATTERY).closer_than(12, nexus)

        if batteries.amount == 0:

            if self.can_afford(U.SHIELDBATTERY):

                await self.build(
                    U.SHIELDBATTERY,
                    near=center.towards(
                        self.start_location,
                        3
                    )
                )

            continue

        # =====================================================
        # Build three Photon Cannons
        # =====================================================

        cannons = self.structures(U.PHOTONCANNON).closer_than(15, nexus)

        cannon_positions = [
            center + Point2((4, 0)),
            center + Point2((-4, 0)),
            center + Point2((0, 4)),
        ]

        for pos in cannon_positions:

            if cannons.closer_than(2, pos).exists:
                continue

            if self.can_afford(U.PHOTONCANNON):

                await self.build(
                    U.PHOTONCANNON,
                    near=pos
                )

                break


    async def manage_expansions(self):

     MAX_BASES = 4

    # =====================================================
    # Initialize variables
    # =====================================================

     if not hasattr(self, "reserved_workers"):
        self.reserved_workers = set()

     if not hasattr(self, "expansion_started"):
        self.expansion_started = False

     if not hasattr(self, "circle_index"):
        self.circle_index = 0

    # =====================================================
    # Find next expansion
    # =====================================================

     if not hasattr(self, "waiting_expansion"):

        self.waiting_expansion = await self.get_next_expansion()

        if self.waiting_expansion is None:
            return

    # =====================================================
    # Reserve one Probe
    # =====================================================

     if not hasattr(self, "expansion_probe"):

        if not self.workers.exists:
            return

        probe = self.workers.closest_to(self.waiting_expansion)

        self.expansion_probe = probe.tag
        self.reserved_workers.add(probe.tag)

        return

     probe = self.workers.find_by_tag(self.expansion_probe)

     if probe is None:
         return

    # =====================================================
    # Wait until first Stargate is complete
    # =====================================================

     if not self.structures(U.STARGATE).ready.exists:
        return

    # =====================================================
    # Keep probe alive at third base
    # =====================================================

     if not self.expansion_started:

        # If we have three bases, hide at the third.
        if self.townhalls.ready.amount >= 3:

            bases = sorted(
                self.townhalls.ready,
                key=lambda n: n.distance_to(self.start_location)
            )

            third_base = bases[2]

            center = third_base.position

        else:
            # Otherwise hide near the natural.
            center = self.townhalls.ready.closest_to(
                self.waiting_expansion
            ).position

        circle = [
            center + Point2((5, 0)),
            center + Point2((0, 5)),
            center + Point2((-5, 0)),
            center + Point2((0, -5)),
        ]

        target = circle[self.circle_index]

        if probe.distance_to(target) < 1:

            self.circle_index = (
                self.circle_index + 1
            ) % len(circle)

            target = circle[self.circle_index]

        probe.move(target)

    # =====================================================
    # Build Nexus
    # =====================================================

     if (
        self.townhalls.amount < MAX_BASES
        and not self.expansion_started
        and self.can_afford(U.NEXUS)
     ):

        probe.build(
            U.NEXUS,
            self.waiting_expansion
        )

        self.expansion_started = True

        self.reserved_workers.discard(probe.tag)

    # =====================================================
    # Continue developing completed expansions
    # =====================================================

     await self.develop_expansions()

    async def build_assimilators_safe(self):

    # Need a Nexus
     if not self.townhalls.ready.exists:
        return


     nexus = self.townhalls.first


    # =====================================================
    # Only use starting base geysers
    # =====================================================

     geysers = self.vespene_geyser.closer_than(
        15,
        nexus.position
     )


    # =====================================================
    # Build Assimilators
    # =====================================================

     for geyser in geysers:


        # Already has one here
        if self.structures(U.ASSIMILATOR).closer_than(
            1,
            geyser.position
        ).exists:

            continue


        # Avoid duplicate construction orders
        if self.already_pending(U.ASSIMILATOR):
            return


        if not self.can_afford(U.ASSIMILATOR):
            return


        # Do not use expansion probe
        workers = self.workers


        if hasattr(self, "expansion_probe"):

            workers = workers.filter(
                lambda w: w.tag != self.expansion_probe
            )


        worker = workers.closest_to(
            geyser.position
        )


        if worker:

            worker.build(
                U.ASSIMILATOR,
                geyser
            )

            return



    # =====================================================
    # Fill gas (maximum 3 workers each)
    # =====================================================

     workers = self.workers


     if hasattr(self, "expansion_probe"):

        workers = workers.filter(
            lambda w: w.tag != self.expansion_probe
        )


     for assimilator in self.structures(U.ASSIMILATOR).ready:


        if assimilator.assigned_harvesters >= 3:
            continue


        needed = 3 - assimilator.assigned_harvesters


        available = workers.sorted_by_distance_to(
            assimilator
        )


        for worker in available:


            if needed <= 0:
                break


            # Don't pull workers already on gas
            if worker.is_gathering:

                continue


            worker.gather(
                assimilator
            )

            needed -= 1


    # ---------- MAIN LOOP ----------

    async def on_step(self, iteration: int):

        await self.build_pylons()
        await self.manage_workers()
        await self.build_choke_cannons()
        await self.manage_zealots()
        await self.manage_buildings()
        await self.build_assimilators_safe()
       # await self.manage_expansions() #also calls on develop_expansions
        await self.manage_carriers()
     
       

        
        


# Run the game
if __name__ == "__main__":
    run_game(
        map_path,
        [Bot(Race.Protoss, SimpleProtossBot()), Computer(Race.Terran, Difficulty.Easy)],
        realtime=True,
    )

# Structures  instead of Units - for buildings 
# Units for Litlle Moving Things
# =============================================================================
# OWAIN'S COMMENT - SUGGESTED FIX (COMMENTED OUT, SO THIS DOES NOT RUN)
# =============================================================================
# Alexandra's active code above is unchanged. BurnySC2 7 separates mobile units
# from buildings. Pylons and Assimilators therefore need to be checked through
# self.structures instead of self.units. Otherwise the completed Pylon count can
# remain zero and the bot can keep ordering another Pylon.
#
# Suggested replacement for build_initial_pylon:
#
# async def build_initial_pylon(self):
#     if (
#         self.structures(U.PYLON).amount == 0
#         and self.can_afford(U.PYLON)
#         and not self.already_pending(U.PYLON)
#     ):
#         choke = self.main_base_ramp.top_center
#         safe_pos = choke.towards(self.start_location, distance=3)
#         await self.build(U.PYLON, near=safe_pos)
#
# Suggested replacement inside fill_gas:
#
# for assim in self.structures(U.ASSIMILATOR).ready:
#     while (
#         assim.assigned_harvesters < assim.ideal_harvesters
#         and self.workers.idle.exists
#     ):
#         worker = self.workers.idle.random
#         worker.gather(assim)
# =============================================================================
