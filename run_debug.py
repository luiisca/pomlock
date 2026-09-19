import sys
# Replace the timer_engine module with our debug version
sys.modules['pomlock.timer_engine'] = __import__('pomlock.timer_engine_debug')
# Now import the app
from pomlock.ui.app import PomlockApp
app = PomlockApp()
app.run()
