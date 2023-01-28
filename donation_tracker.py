import os
import json
import asyncio
import requests


class DonationsTracker:
    def __init__(self, donation_event_callback=None):
        self.curr_amount = None
        self.running = False
        self.donation_event_callback = donation_event_callback
    
    async def run(self):
        if not self.running:
            self.running = True
        
        while self.running:
            new_amount = self.retrieve_amount()
            if new_amount:
                if new_amount != self.curr_amount:
                    print(f"[DonationsTracker] New donation detected! ({self.curr_amount} -> {new_amount})")
                    #await self.donation_event_callback()
                    if self.curr_amount != None and self.donation_event_callback:
                        print(f"[DonationsTracker] Calling callback {self.donation_event_callback}")
                        await self.donation_event_callback()

                    self.curr_amount = new_amount
                    self.write_to_disk()

            await asyncio.sleep(5)

    def retrieve_amount(self):
        r = requests.get("https://piquetdestream-api.fly.dev/v1/counter/state")
        if r:
            new_amount = r.json().get("amount", None)
            if new_amount:
                return new_amount
        
        return None

    def load_from_disk(self):
        if os.path.exists("donations_state.json"):
            fp = open("donations_state.json", "r")
            data = json.load(fp)
            self.curr_amount = data.get("amount", None)
            fp.close()
    
    def write_to_disk(self):
        fp = open("donations_state.json", "w")
        fp.write(json.dumps({"amount": self.curr_amount}, indent=4))
        fp.close()


if __name__ == "__main__":
    def _test():
        print("owey")

    d = DonationsTracker(donation_event_callback=_test)
    asyncio.get_event_loop().run_until_complete(d.run())
