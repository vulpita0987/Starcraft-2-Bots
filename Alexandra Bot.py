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
        self.zealot_attack_group = []
        self.zealot_defend_group = []
        self.patrol_points = []
        self.carrier_groups = []
        

    async def on_start(self):
     nexus = self.townhalls.first
     choke = self.main_base_ramp.top_center

    # Patrol points covering your whole base
     self.patrol_points = [
        nexus.position + Point2((8, 0)),
        nexus.position + Point2((-8, 0)),
        nexus.position + Point2((0, 8)),
        nexus.position + Point2((0, -8)),
        choke
    ]


    # ---------- PYLONS (MAX 5) ----------

    
    async def build_initial_pylon(self):
     if (
         self.structures(U.PYLON).amount == 0
         and self.can_afford(U.PYLON)
         and not self.already_pending(U.PYLON)
     ):
         choke = self.main_base_ramp.top_center
         safe_pos = choke.towards(self.start_location, distance=3)
         await self.build(U.PYLON, near=safe_pos)



   # ------WORKERS------
    async def build_workers(self):
        # OWAIN'S COMMENT: Build 16 mineral workers plus 6 gas workers.
        worker_target = 22

        # Build probes until we reach 22 workers
        if self.workers.amount < worker_target and self.can_afford(U.PROBE) and self.supply_left > 0:
            for nexus in self.townhalls.ready.idle:
                nexus.train(U.PROBE)
                return
            




    async def handle_idle_workers(self):
    # Only run allocation if at least one worker is idle
     if not self.workers.idle.exists:
        return

    # --- Step 1: Keep 16 workers on minerals ---
     minerals = self.mineral_field.closer_than(20, self.start_location)
     if minerals:
        mineral_spots = minerals

    # Count how many workers are already mining
     mining_workers = []
     for w in self.workers:
        if w.is_collecting and w.order_target in {m.tag for m in mineral_spots}:
            mining_workers.append(w)

    # Assign idle workers to minerals until we reach 16
     needed_mineral_workers = 16 - len(mining_workers)
     if needed_mineral_workers > 0:
        for w in self.workers.idle[:needed_mineral_workers]:
            w.gather(mineral_spots.closest_to(w))

    # --- Step 2: Assign 3 workers per assimilator ---
     for assim in self.structures(U.ASSIMILATOR).ready:
        # Count workers already gathering gas from this assimilator
        gas_workers = []
        for w in self.workers:
            if w.is_collecting and w.order_target == assim.tag:
                gas_workers.append(w)

        # Assign idle workers until we reach 3
        needed_gas_workers = 3 - len(gas_workers)
        if needed_gas_workers > 0:
            for w in self.workers.idle[:needed_gas_workers]:
                w.gather(assim)


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





    

    async def build_corner_pylons(self):
    # You already have 1 Nexus, use it as the center
     if not self.townhalls.ready.exists:
        return

     nexus = self.townhalls.first

    # Stop once 4 pylons are built (not counting the choke pylon)
     if self.structures(U.PYLON).amount >= 5:  # 1 choke + 4 corners
        return

    # Four simple corner positions around the Nexus
     corner_positions = [
        nexus.position + Point2((10, 10)),
        nexus.position + Point2((-10, 10)),
        nexus.position + Point2((10, -10)),
        nexus.position + Point2((-10, -10)),
     ]
 
    # Try each corner until all 4 are placed
     for pos in corner_positions:
        # If we already have 5 pylons total (1 choke + 4 corners), stop
        if self.structures(U.PYLON).amount >= 5:
            return

        if await self.can_place(U.PYLON, pos):
            if self.can_afford(U.PYLON) and not self.already_pending(U.PYLON):
                await self.build(U.PYLON, near=pos)
                # ❌ DO NOT return here — let the loop continue



    async def build_gateway(self):
    # Build a Gateway near your existing Nexus
     if not self.townhalls.ready.exists:
        return

    # Only build 1 Gateway
     if self.structures(U.GATEWAY).amount >= 1:
        return

     nexus = self.townhalls.first

     if self.can_afford(U.GATEWAY) and not self.already_pending(U.GATEWAY):
        await self.build(U.GATEWAY, near=nexus.position)

    async def build_forge(self):
    # You already have 1 Nexus, use it as the center
     if not self.townhalls.ready.exists:
        return

    # Only build 1 Forge
     if self.structures(U.FORGE).amount >= 1:
        return

     nexus = self.townhalls.first

    # Build the Forge near the Nexus
     if self.can_afford(U.FORGE) and not self.already_pending(U.FORGE):
        await self.build(U.FORGE, near=nexus.position)






    



   
    


    async def build_supply_pylon(self):
     if self.supply_left < 4 and self.structures(U.PYLON).amount >= 2:
        if self.already_pending(U.PYLON) >= 3:
            return

        if not self.can_afford(U.PYLON):
            return

        if not self.townhalls.ready.exists:
            return

        nexus = self.townhalls.first

        # ALL your base structures (correct call)
        base_structures = self.structures.closer_than(30, nexus.position)

        edge_positions = []
        for s in base_structures:
            edge_positions.append(s.position + Point2((4, 0)))
            edge_positions.append(s.position + Point2((-4, 0)))
            edge_positions.append(s.position + Point2((0, 4)))
            edge_positions.append(s.position + Point2((0, -4)))

        choke = self.main_base_ramp.top_center
        edge_positions.append(choke + Point2((4, 0)))
        edge_positions.append(choke + Point2((-4, 0)))

        for pos in edge_positions:
            if await self.can_place(U.PYLON, pos):
                await self.build(U.PYLON, near=pos)
                return




    async def build_cybercore(self):
    # Need a Gateway first
     if not self.structures(U.GATEWAY).ready.exists:
        return

    # Only build 1 Cybercore
     if self.structures(U.CYBERNETICSCORE).exists or self.already_pending(U.CYBERNETICSCORE):
        return

    # Need minerals
     if not self.can_afford(U.CYBERNETICSCORE):
        return

     nexus = self.townhalls.first

    # Build near Nexus
     await self.build(U.CYBERNETICSCORE, near=nexus.position)


    async def build_stargate(self):
    # Need Cybercore first
     if not self.structures(U.CYBERNETICSCORE).ready.exists:
        return

     # Only build 1 Stargate
     if self.structures(U.STARGATE).exists or self.already_pending(U.STARGATE):
        return

    # Need minerals + gas
     if not self.can_afford(U.STARGATE):
        return

     nexus = self.townhalls.first

     await self.build(U.STARGATE, near=nexus.position)

    async def build_fleet_beacon(self):
    # Need Stargate first
     if not self.structures(U.STARGATE).ready.exists:
        return

    # Only build 1 Fleet Beacon
     if self.structures(U.FLEETBEACON).exists or self.already_pending(U.FLEETBEACON):
        return

    # Need minerals + gas
     if not self.can_afford(U.FLEETBEACON):
        return

     nexus = self.townhalls.first

     await self.build(U.FLEETBEACON, near=nexus.position)

  


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

    # Need gateway
     if not self.structures(U.GATEWAY).ready.exists:
        return

     gateway = self.structures(U.GATEWAY).ready.first


    # Keep producing zealots
     if (
        self.can_afford(U.ZEALOT)
        and gateway.is_idle
        and self.supply_left > 0
     ):
        gateway.train(U.ZEALOT)


    # ----------------------------
    # Attack with all zealots
    # ----------------------------

     zealots = self.units(U.ZEALOT)

     if zealots.amount == 0:
        return


    # If enemy buildings are visible, destroy them
     if self.enemy_structures.exists:

        target = self.enemy_structures.closest_to(
            zealots.center
        )


    # Otherwise go to enemy starting location
     else:

        target = self.enemy_start_locations[0]


    # Send every zealot forward
     for zealot in zealots:

        if zealot.is_idle:

            zealot.attack(target)



   

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
    # Build workers
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
    # Mineral patches around the Nexus
    # =====================================================
     minerals = self.mineral_field.closer_than(20, nexus.position)

     if not minerals:
        return

     mineral_tags = {m.tag for m in minerals}

    # =====================================================
    # Fill Assimilators (3 workers each)
    # =====================================================
     for assim in self.structures(U.ASSIMILATOR).ready:

        gas_workers = self.workers.filter(
            lambda w: w.is_collecting and w.order_target == assim.tag
        )

        while gas_workers.amount < 3:

            mineral_workers = self.workers.filter(
                lambda w: (
                    w.is_collecting
                    and w.order_target in mineral_tags
                )
            )

            if not mineral_workers.exists:
                break

            worker = mineral_workers.closest_to(assim)
            worker.gather(assim)

            gas_workers = self.workers.filter(
                lambda w: w.is_collecting and w.order_target == assim.tag
            )

    # =====================================================
    # Send idle workers to minerals
    # =====================================================
     for worker in self.workers.idle:
        worker.gather(minerals.closest_to(worker))

    # ---------- MAIN LOOP ----------

    async def on_step(self, iteration: int):

        #await self.build_initial_pylon()
        #await self.build_corner_pylons()
        #await self.build_supply_pylon()
        await self.build_pylons()

        #await self.build_workers()
        #await self.handle_idle_workers()
        await self.manage_workers()

        await self.build_choke_cannons()

        await self.manage_zealots()
        #--
        await self.build_forge()
        await self.build_gateway()
        await self.build_cybercore()
        await self.build_stargate()
        await self.build_fleet_beacon()

        await self.build_assimilators_safe()

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
