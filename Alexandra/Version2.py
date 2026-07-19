#Core bot and run loop
from sc2.bot_ai import BotAI                # Base bot class (your AI inherits this)
from sc2.main import run_game               # To actually start the game

#Game setup
from sc2.data import Race, Difficulty, Result
from sc2.player import Bot, Computer, Human
from sc2 import maps                        # For ladder maps and map lookups
from pathlib import Path                    # For custom/local maps

#Units, structures, and abilities
from sc2.ids.unit_typeid import UnitTypeId as U      # e.g., U.PROBE, U.NEXUS
from sc2.ids.ability_id import AbilityId             # For casting abilities (chronoboost, etc.)
from sc2.ids.buff_id import BuffId                   # For buffs like CHRONOBOOSTENERGYCOST
from sc2.ids.upgrade_id import UpgradeId             # For upgrades like WARPGATERESEARCH
#Alex
#Positioning & geometry
from sc2.position import Point2, Point3              # Used for coordinates, pathing
from sc2.unit import Unit                            # Single unit object
from sc2.units import Units                          # Collection of units

#Events and game state
from sc2.game_info import GameInfo
from sc2.game_state import GameState

from sc2.unit_command import UnitCommand


from sc2.ids.ability_id import AbilityId
import math
#Debugging (optional)
from sc2.client import Client                       # For debug drawing, pings, etc.

from sc2.position import Point2
# Use a built-in map
map_path = maps.get("AbyssalReefLE")  # returns a Map object
# Or if you have a local map file
# map_path = Path("D:/Maps/MyMap.SC2Map")


class SimpleProtossBot(BotAI):
    async def on_start(self):
        print("Protoss bot started!")
    
    async def build_pylons(self):
    # Calculate how close we are to maxing out supply
     if self.supply_used >= self.supply_cap * 0.8 and self.can_afford(U.PYLON) and self.units(U.GATEWAY).amount > 1 and not self.already_pending(U.PYLON):
        nexus = self.townhalls.ready.random
        await self.build(U.PYLON, near=nexus.position.towards(self.game_info.map_center, distance=5))

  

    async def cannon_near_choke_point_pylon(self):
     if  self.can_afford(U.PYLON) and self.units(U.NEXUS).amount and not self.already_pending(U.PYLON) and self.units(U.PYLON).amount == 0: 
        # Get the ramp object
        ramp = self.main_base_ramp

        # Choose a point slightly behind the ramp's top for safe placement
        pylon_pos = ramp.top_center.towards(self.start_location, distance=3)

        await self.build(U.PYLON, near=pylon_pos)
        
  

    async def build_cannon_at_choke(self):
    # Make sure you can afford it and don't already have one there
     if self.can_afford(U.PHOTONCANNON) and self.units(U.PHOTONCANNON).amount < 6:
        # Find a ready Pylon near the choke point
        pylons = self.units(U.PYLON).ready
        if pylons:
            # Choose the closest Pylon to your choke point
            choke_pylon = pylons.closest_to(self.main_base_ramp.top_center)

            # Build the Cannon near that Pylon
            await self.build(U.PHOTONCANNON, near=choke_pylon.position.towards(self.main_base_ramp.top_center, distance=2))


    async def build_forge_near_main_base(self):
    # Check if you can afford a Forge and don't already have one
     if self.can_afford(U.FORGE) and not self.units(U.FORGE).exists:
        # Find a Pylon manually using units
        pylons = self.units(U.PYLON).ready
        if pylons:
            # Choose the one closest to your start location
            pylon = pylons.closest_to(self.start_location)
            # Place Forge near that Pylon
            await self.build(U.FORGE, near=pylon.position.towards(self.game_info.map_center, distance=4))
        else:
            # No Pylons yet—build one near your start location
            if self.can_afford(U.PYLON):
                await self.build(U.PYLON, near=self.start_location)

 

    

   

    async def place_perimeter_pylons(self):
     nexus = self.townhalls.first
     radius = 12  # Distance from Nexus
     count = 4    # Number of pylons to place in a ring

     for i in range(count):
        angle = 2 * math.pi * i / count
        dx = radius * math.cos(angle)
        dy = radius * math.sin(angle)
        pos = nexus.position + Point2((dx, dy))

        if await self.can_place(U.PYLON, pos) and self.units(U.PYLON).closer_than(3, pos).amount == 0:
            if self.can_afford(U.PYLON):
                await self.build(U.PYLON, near=pos)



    async def build_main_base_pylon(self):
    # Only build if you don't already have one in the main base
     if self.can_afford(U.PYLON) and self.units(U.PYLON).closer_than(12, self.start_location).amount == 0:
        # Choose a position slightly offset from your start location
        pylon_pos = self.start_location.towards(self.game_info.map_center, distance=5)

        # Check if the location is buildable
        if await self.can_place(U.PYLON, pylon_pos):
            await self.build(U.PYLON, near=pylon_pos)


    

    async def build_workers(self):
     ideal = sum(h.ideal_harvesters for h in self.townhalls.ready)
     target = min(ideal, 44)

     if self.workers.amount >= target or self.supply_left <= 0 or not self.can_afford(U.PROBE):
        return
     if not self.townhalls.ready:
        return

     for nexus in self.townhalls.ready:
        if nexus.is_idle:
            nexus.train(U.PROBE)
            print(f"[{self.time:.1f}] SENT: Probe at Nexus {nexus.tag}")
            return

    async def expand(self):
        # If we can afford a Nexus and have less than 3, expand
        if self.townhalls.amount <= 1 and self.can_afford(U.NEXUS):
            await self.expand_now()

    async def build_gateway_in_main_base(self):
     if self.can_afford(U.GATEWAY) and self.units(U.GATEWAY).amount < 2:
        main_base_pylons = self.units(U.PYLON).ready.closer_than(12, self.start_location)
        if main_base_pylons:
            pylon = main_base_pylons.closest_to(self.start_location)
            offset_pos = pylon.position.towards(self.game_info.map_center, distance=3)

            if await self.can_place(U.GATEWAY, offset_pos):
                await self.build(U.GATEWAY, near=offset_pos)
            else:
                print(f"Cannot place Gateway at {offset_pos}, trying fallback...")
                placement = await self.find_placement(U.GATEWAY, near=pylon.position, max_distance=6, random_alternative=True)
                if placement:
                    await self.build(U.GATEWAY, placement)
                else:
                    print("No valid placement found for Gateway.")

    async def train_zealots(self):
     zealot_goal = 20
     if self.units(U.GATEWAY).ready.exists:
        for gateway in self.units(U.GATEWAY).ready.idle:
            if self.can_afford(U.ZEALOT) and self.units(U.ZEALOT).amount < zealot_goal:
                gateway.train(U.ZEALOT)

    async def split_zealots(self):
     zealots = self.units(U.ZEALOT)
    
     if zealots.amount >= 20:
        # Sort by proximity to your base to keep the closest 5
        zealots_sorted = zealots.sorted_by_distance_to(self.start_location)
        defenders = zealots_sorted[:5]
        attackers = zealots_sorted[5:]

        # Defenders hold position near main base
        for zealot in defenders:
            zealot.move(self.start_location)

        # Attackers move toward enemy base
        if self.enemy_start_locations:
            target = self.enemy_start_locations[0]
            for zealot in attackers:
                zealot.attack(target)

    async def on_step(self, iteration: int):
        await self.build_pylons()
        await self.build_workers()
        await self.build_main_base_pylon()
        await self.expand()
        await self.cannon_near_choke_point_pylon()
        await self.build_forge_near_main_base()
        await self.build_cannon_at_choke()
        await self.place_perimeter_pylons()
        await self.build_gateway_in_main_base()
        await self.train_zealots()
        await self.split_zealots()
        


   
 

# Run the game
if __name__ == "__main__":
    run_game(
    map_path,
    [Bot(Race.Protoss, SimpleProtossBot()), Computer(Race.Terran, Difficulty.Easy)],
    realtime=True,
)

