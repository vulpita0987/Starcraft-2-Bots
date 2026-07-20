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

    async def on_start(self):
        print("Protoss bot started!")
#AI Garbage - to be done from scratch
    # ---------- PYLONS (MAX 5) ----------

    async def build_initial_pylon(self):
        # Build ONLY the first pylon near the Nexus
        if self.units(U.PYLON).amount == 0 and self.can_afford(U.PYLON) and not self.already_pending(U.PYLON):
            await self.build(U.PYLON, near=self.start_location)


    # ---------- CANNONS AT CHOKE ----------

    async def build_choke_cannons(self):
        choke = self.main_base_ramp.top_center

        # If no pylons exist, build one near the choke first
        if not self.units(U.PYLON).ready.exists:
            if self.can_afford(U.PYLON) and not self.already_pending(U.PYLON):
                await self.build(U.PYLON, near=choke)
            return

        # Use the closest pylon to the choke
        pylon = self.units(U.PYLON).ready.closest_to(choke)

        # Always try to build cannons near the choke
        if self.can_afford(U.PHOTONCANNON):
            await self.build(U.PHOTONCANNON, near=pylon.position.towards(choke, distance=2))

    # ---------- WORKERS & IDLE HANDLING ----------

    async def build_workers(self):
        if not self.townhalls.ready:
            return

        ideal = sum(t.ideal_harvesters for t in self.townhalls.ready)
        target = min(ideal, 44)

        if self.workers.amount < target and self.can_afford(U.PROBE) and self.supply_left > 0:
            for nexus in self.townhalls.ready.idle:
                nexus.train(U.PROBE)
                return

    async def handle_idle_workers(self):
        for worker in self.workers.idle:
            # Prefer gas if not saturated
            gas = self.units(U.ASSIMILATOR).ready.filter(
                lambda a: a.assigned_harvesters < a.ideal_harvesters
            )
            if gas:
                worker.gather(gas.closest_to(worker))
            else:
                minerals = self.mineral_field.closer_than(20, self.start_location)
                if minerals:
                    worker.gather(minerals.closest_to(worker))

    # ---------- GAS ----------

    async def build_assimilators(self):
        # Only start gas after 2 pylons
        if self.units(U.PYLON).amount < 2:
            return

        for geyser in self.vespene_geyser.closer_than(15, self.start_location):
            if not self.units(U.ASSIMILATOR).closer_than(1, geyser).exists:
                if self.can_afford(U.ASSIMILATOR):
                    await self.build(U.ASSIMILATOR, geyser)
                    return

    async def fill_gas(self):
        for assim in self.units(U.ASSIMILATOR).ready:
            while assim.assigned_harvesters < assim.ideal_harvesters and self.workers.idle.exists:
                worker = self.workers.idle.random
                worker.gather(assim)

    # ---------- GATEWAYS ----------

    async def build_gateways(self):
        if self.units(U.GATEWAY).amount >= 2:
            return

        pylons = self.units(U.PYLON).ready
        if pylons.exists and self.can_afford(U.GATEWAY):
            await self.build(U.GATEWAY, near=pylons.random)

    # ---------- ARMY (ZEALOTS) ----------

    async def train_zealots(self):
        # Always keep training zealots if we have gateways and supply
        for gw in self.units(U.GATEWAY).ready.idle:
            if self.can_afford(U.ZEALOT) and self.supply_left > 0:
                gw.train(U.ZEALOT)

    async def split_first_wave(self):
        zealots = self.units(U.ZEALOT)

        if zealots.amount < 20:
            return

        sorted_zealots = zealots.sorted_by_distance_to(self.start_location)
        defenders = sorted_zealots[:5]
        attackers = sorted_zealots[5:20]

        for z in defenders:
            z.move(self.start_location)

        if self.enemy_start_locations:
            target = self.enemy_start_locations[0]
            for z in attackers:
                z.attack(target)

    async def split_followup_waves(self):
        zealots = self.units(U.ZEALOT)

        # After first 20, every extra 20 → 10 attack, 10 defend
        if zealots.amount < 40:
            return

        new_zealots = zealots.sorted_by_distance_to(self.start_location)[20:]

        if len(new_zealots) >= 20:
            defenders = new_zealots[:10]
            attackers = new_zealots[10:20]

            for z in defenders:
                z.move(self.start_location)

            if self.enemy_start_locations:
                target = self.enemy_start_locations[0]
                for z in attackers:
                    z.attack(target)

    # ---------- MAIN LOOP ----------

    async def on_step(self, iteration: int):
        await self.build_initial_pylon()
        await self.build_base_pylons()
        await self.build_choke_cannons()
        await self.build_workers()
        await self.build_assimilators()
        await self.fill_gas()
        await self.build_gateways()
        await self.train_zealots()
        await self.split_first_wave()
        await self.split_followup_waves()
        await self.handle_idle_workers()


# Run the game
if __name__ == "__main__":
    run_game(
        map_path,
        [Bot(Race.Protoss, SimpleProtossBot()), Computer(Race.Terran, Difficulty.Easy)],
        realtime=True,
    )