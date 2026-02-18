#import cProfile
from modules.app_core import *
app = HomeApp()
app.exec()
#cProfile.run('app.exec()', 'profile_output')