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
     choke = self.main_base_ramp.top_center

    # Stop at 5 cannons
     if self.structures(U.PHOTONCANNON).amount >= 5:
        return

    # Must have a pylon powering the choke
     if not self.structures(U.PYLON).ready.exists:
        return

     pylon = self.structures(U.PYLON).ready.closest_to(choke)

    # Try 5 simple offsets that avoid blocking the ramp
     positions = [
        pylon.position.towards(choke, 4),
        pylon.position.towards(choke, 4) + Point2((2, 0)),
        pylon.position.towards(choke, 4) + Point2((-2, 0)),
        pylon.position.towards(choke, 4) + Point2((0, 2)),
        pylon.position.towards(choke, 4) + Point2((0, -2)),
     ]

     for pos in positions:
        if self.structures(U.PHOTONCANNON).amount >= 5:
            return

        # Let the engine find a valid tile NEAR the safe offset
     existing = self.structures(U.PHOTONCANNON).amount
     pending = self.already_pending(U.PHOTONCANNON)

     if existing + pending < 5:
       if self.can_afford(U.PHOTONCANNON):
        await self.build(U.PHOTONCANNON, near=pos)



    async def build_assimilators_safe(self):
    # Must have a Nexus
     if not self.townhalls.ready.exists:
        return

     nexus = self.townhalls.first

    # CORRECT geyser selection for BurnySC2
     # OWAIN'S COMMENT: Only use the two geysers at the starting Nexus.
     geysers = self.vespene_geyser.closer_than(15, nexus.position)

    # Build ONE assimilator per frame
     for geyser in geysers:
        # If no assimilator exists here, build one
        if not self.structures(U.ASSIMILATOR).closer_than(1, geyser.position).exists and self.can_afford(U.ASSIMILATOR):
            # OWAIN'S COMMENT: select_build_worker reads unsupported order data here.
            worker = self.workers.closest_to(geyser.position)
            if worker:
                worker.build(U.ASSIMILATOR, geyser)
                break

     # OWAIN'S COMMENT: BurnySC2's distribute_workers crashes on this SC2 version.
     # Send Probes to completed Assimilators without using that helper.
     for assimilator in self.structures(U.ASSIMILATOR).ready:
      if assimilator.assigned_harvesters < assimilator.ideal_harvesters:
       self.workers.closest_to(assimilator).gather(assimilator)



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

    # =====================================================
    # Build Probes
    # =====================================================

     gas_target = self.structures(U.ASSIMILATOR).ready.amount * 3
     worker_target = 16 + gas_target

     if (
        self.workers.amount < worker_target
        and self.can_afford(U.PROBE)
        and self.supply_left > 0
        and nexus.is_idle
     ):
        nexus.train(U.PROBE)

    # =====================================================
    # Nearby mineral patches
    # =====================================================

     minerals = self.mineral_field.closer_than(20, nexus)

     if not minerals.exists:
        return

    # =====================================================
    # Fill Assimilators
    # =====================================================

     for assim in self.structures(U.ASSIMILATOR).ready:

        # Count workers already close to this Assimilator
        nearby_workers = self.workers.closer_than(3, assim)

        if nearby_workers.amount >= 3:
            continue

        needed = 3 - nearby_workers.amount

        candidates = self.workers.sorted_by_distance_to(assim)

        for worker in candidates[:needed]:
            worker.gather(assim)

    # =====================================================
    # Idle workers mine minerals
    # =====================================================

     for worker in self.workers.idle:
        worker.gather(minerals.closest_to(worker))


    async def manage_buildings(self):

     if not self.townhalls.ready.exists:
        return

     nexus = self.townhalls.ready.first
     center = self.game_info.map_center

    # Building positions (spread out to leave room for units)
     forge_pos = nexus.position.towards(center, 6)
     gateway_pos = nexus.position.towards(center, 10)
     cyber_pos = nexus.position.towards(center, 14)
     stargate_pos = nexus.position.towards(center, 18)
     fleet_pos = nexus.position.towards(center, 22)

    # ==========================================================
    # 1. Forge
    # ==========================================================
     if self.structures(U.FORGE).amount == 0:
        if self.can_afford(U.FORGE):
            await self.build(U.FORGE, near=forge_pos)
        return

    # ==========================================================
    # 2. Build 3 Photon Cannons
    # ==========================================================
     if self.structures(U.PHOTONCANNON).amount < 3:

        if self.can_afford(U.PHOTONCANNON):

            # Build each cannon a little further from the Nexus
            distance = 7 + self.structures(U.PHOTONCANNON).amount * 2

            cannon_pos = nexus.position.towards(center, distance)

            await self.build(U.PHOTONCANNON, near=cannon_pos)

        return

    # Wait until all 3 cannons are finished
     if self.structures(U.PHOTONCANNON).ready.amount < 3:
        return

    # ==========================================================
    # 3. Gateway
    # ==========================================================
     if self.structures(U.GATEWAY).amount == 0:
        if self.can_afford(U.GATEWAY):
            await self.build(U.GATEWAY, near=gateway_pos)
        return

    # ==========================================================
    # 4. Cybernetics Core
    # ==========================================================
     if (
        self.structures(U.GATEWAY).ready.exists
        and self.structures(U.CYBERNETICSCORE).amount == 0
     ):
        if self.can_afford(U.CYBERNETICSCORE):
            await self.build(U.CYBERNETICSCORE, near=cyber_pos)
        return

    # ==========================================================
    # 5. Stargate
    # ==========================================================
     if (
        self.structures(U.CYBERNETICSCORE).ready.exists
        and self.structures(U.STARGATE).amount == 0
     ):
        if self.can_afford(U.STARGATE):
            await self.build(U.STARGATE, near=stargate_pos)
        return

    # ==========================================================
    # 6. Fleet Beacon
    # ==========================================================
     if (
        self.structures(U.STARGATE).ready.exists
        and self.structures(U.FLEETBEACON).amount == 0
     ):
        if self.can_afford(U.FLEETBEACON):
            await self.build(U.FLEETBEACON, near=fleet_pos)


    async def develop_expansions(self):

    # Don't develop until Fleet Beacon exists
     if not self.structures(U.FLEETBEACON).ready.exists:
        return

     for nexus in self.townhalls.ready:

        # Skip the starting base
        if nexus == self.townhalls.first:
            continue

        center = nexus.position.towards(self.game_info.map_center, 6)

        # =====================================================
        # Assimilators (2)
        # =====================================================

        geysers = self.vespene_geyser.closer_than(12, nexus)

        for geyser in geysers:

            if not self.structures(U.ASSIMILATOR).closer_than(1, geyser).exists:

                if self.can_afford(U.ASSIMILATOR):

                    worker = self.select_build_worker(geyser.position)

                    if worker:
                        worker.build(U.ASSIMILATOR, geyser)

        # =====================================================
        # One Pylon
        # =====================================================

        pylons = self.structures(U.PYLON).closer_than(10, nexus)

        if pylons.amount == 0:

            if self.can_afford(U.PYLON):

                await self.build(
                    U.PYLON,
                    near=center
                )

            continue

        # Wait until powered
        if not pylons.ready.exists:
            continue

        # =====================================================
        # Two Stargates
        # =====================================================

        stargates = self.structures(U.STARGATE).closer_than(15, nexus)

        while (
            stargates.amount + self.already_pending(U.STARGATE) < 2
            and self.can_afford(U.STARGATE)
        ):

            pos = center.towards(
                self.game_info.map_center,
                4 + stargates.amount * 4
            )

            await self.build(U.STARGATE, near=pos)
            return

        # =====================================================
        # One Shield Battery
        # =====================================================

        batteries = self.structures(U.SHIELDBATTERY).closer_than(12, nexus)

        if batteries.amount == 0:

            if self.can_afford(U.SHIELDBATTERY):

                await self.build(
                    U.SHIELDBATTERY,
                    near=center.towards(self.game_info.map_center, -3)
                )

            return

        # =====================================================
        # Three Photon Cannons
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
                return

    async def manage_expansions(self):

     MAX_BASES = 4

     if (
        self.townhalls.amount + self.already_pending(U.NEXUS) < MAX_BASES
        and self.can_afford(U.NEXUS)
     ):
        await self.expand_now()

     await self.develop_expansions()
    # ---------- MAIN LOOP ----------

    async def on_step(self, iteration: int):

        await self.build_pylons()
        await self.manage_workers()
        await self.build_choke_cannons()
        await self.manage_zealots()
        await self.manage_buildings()
        await self.build_assimilators_safe()
        #await self.manage_expansions() #also calls on develop_expansions
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
