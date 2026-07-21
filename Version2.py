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

    # ---------- PYLONS (MAX 5) ----------

    
    async def build_initial_pylon(self):
      # Build the first pylon near the choke, but not blocking the ramp
      if self.units(U.PYLON).amount == 0 and self.can_afford(U.PYLON) and not self.already_pending(U.PYLON):

        choke = self.main_base_ramp.top_center

        # Move the placement slightly toward your base so it doesn't block the ramp
        safe_pos = choke.towards(self.start_location, distance=3)

        # Build the pylon at the safe choke position
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

    # ---------- MAIN LOOP ----------

    async def on_step(self, iteration: int):
        await self.build_initial_pylon()
        
        await self.build_workers()
        await self.fill_gas()
        await self.handle_idle_workers()


# Run the game
if __name__ == "__main__":
    run_game(
        map_path,
        [Bot(Race.Protoss, SimpleProtossBot()), Computer(Race.Terran, Difficulty.Easy)],
        realtime=True,
    )