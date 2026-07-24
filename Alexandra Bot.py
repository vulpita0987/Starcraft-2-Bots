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
        # Step 1: mineral saturation only (16 workers)
        mineral_target = 16

        # Build probes until we reach 16 workers
        if self.workers.amount < mineral_target and self.can_afford(U.PROBE) and self.supply_left > 0:
            for nexus in self.townhalls.ready.idle:
                nexus.train(U.PROBE)
                return
            
    async def fill_gas(self):
        # Step 2: after assimilators exist, fill gas until full saturation (22 workers total)
        gas_target = 22

        # If we don't have enough workers yet, keep building them
        if self.workers.amount < gas_target and self.can_afford(U.PROBE) and self.supply_left > 0:
            for nexus in self.townhalls.ready.idle:
                nexus.train(U.PROBE)

        # Step 3: assign idle workers to gas
        for assim in self.units(U.ASSIMILATOR).ready:
            while assim.assigned_harvesters < assim.ideal_harvesters and self.workers.idle.exists:
                worker = self.workers.idle.random
                worker.gather(assim)

    async def handle_idle_workers(self):
         for worker in self.workers.idle:
            minerals = self.mineral_field.closer_than(20, self.start_location)
            if minerals:
                worker.gather(minerals.closest_to(worker))

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

    async def build_initial_zealots(self):
    # Only start making zealots after 3 cannons exist
     if self.structures(U.PHOTONCANNON).amount < 3:
        return

    # Stop at 20 zealots for the first batch
     if self.units(U.ZEALOT).amount >= 20:
        return

    # Need a gateway
     if not self.structures(U.GATEWAY).ready.exists:
        return

     gateway = self.structures(U.GATEWAY).ready.first

     if self.can_afford(U.ZEALOT) and gateway.is_idle:
        gateway.train(U.ZEALOT)

    async def patrol_and_defend_base(self):
     zealots = self.units(U.ZEALOT)

     if zealots.amount == 0:
        return

     nexus = self.townhalls.first
     choke = self.main_base_ramp.top_center

    # Find any enemy inside your base area (Nexus → choke)
     threats = self.enemy_units.closer_than(30, nexus.position)

    # If ANY threat exists → all zealots gang up together
     if threats.exists:
        target = threats.closest_to(nexus)
        for z in zealots:
            z.attack(target)
        return

    # BEFORE SPLIT: all zealots gather at choke
     if zealots.amount < 20:
        for z in zealots.idle:
            z.attack(choke)
        return

    # AFTER SPLIT: defenders stay at choke
     for z in self.zealot_defend_group:
        if z.is_idle:
            z.attack(choke)




    
    async def split_zealots(self):
     zealots = self.units(U.ZEALOT)

     if zealots.amount < 20:
        return

    # Only split once
     if len(self.zealot_attack_group) == 10 and len(self.zealot_defend_group) == 10:
        return

    # First 10 defend
     self.zealot_defend_group = zealots[:10]

    # Next 10 attack
     self.zealot_attack_group = zealots[10:20]

    # Send attackers to enemy start
     enemy_base = self.enemy_start_locations[0]
     for z in self.zealot_attack_group:
        z.attack(enemy_base)


    async def build_continuous_zealots(self):
    # Only start continuous production after all 5 cannons exist
     if self.structures(U.PHOTONCANNON).amount < 5:
        return

    # Need a gateway
     if not self.structures(U.GATEWAY).ready.exists:
        return

     gateway = self.structures(U.GATEWAY).ready.first

     if self.can_afford(U.ZEALOT) and gateway.is_idle:
        gateway.train(U.ZEALOT)
    
    async def manage_zealot_groups(self):
     zealots = self.units(U.ZEALOT)

    # Always keep 10 defenders
     defenders = zealots[:10]
     attackers = zealots[10:]

    # Defenders stay at base
     nexus = self.townhalls.first
     for z in defenders:
        z.attack(nexus.position)

    # Every extra 10 attackers go attack
     enemy_base = self.enemy_start_locations[0]
     for z in attackers:
        z.attack(enemy_base)

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

    async def manage_gas_collection(self):
    # Create 6 new workers
     for nexus in self.townhalls.ready.idle:
        if self.can_afford(U.PROBE) and self.supply_left > 0:
            nexus.train(U.PROBE)

    # Build ONE assimilator per frame on geysers near your base
     geysers = self.vespene_geyser.closer_than(20, self.townhalls.first.position)

     for geyser in geysers:
        if not self.structures(U.ASSIMILATOR).closer_than(1, geyser.position).exists:
            await self.build(U.ASSIMILATOR, near=geyser)
            return  # <-- THIS FIXES THE CRASH

    # Send workers to collect gas ONLY from finished assimilators
     for assim in self.structures(U.ASSIMILATOR).ready:
        for worker in self.workers.idle:
            worker.gather(assim)












    # ---------- MAIN LOOP ----------

    async def on_step(self, iteration: int):
        await self.build_initial_pylon()
        await self.build_corner_pylons()
        await self.build_workers()
        #await self.fill_gas()
        await self.handle_idle_workers()
        await self.build_forge()
        await self.build_gateway()
        await self.build_choke_cannons()
        await self.build_initial_zealots()
        await self.patrol_and_defend_base()
        await self.split_zealots()
        await self.build_continuous_zealots()
        await self.manage_zealot_groups()
        await self.build_supply_pylon()
        await self.build_cybercore()
        await self.build_stargate()
        await self.build_fleet_beacon()
        await self.manage_gas_collection() #error

        
        


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
