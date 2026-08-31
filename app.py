import cProfile
from modules.app_core import *

DO_PROFILING = True

# make the app
app = HomeApp()

if DO_PROFILING:
    cProfile.run('app.exec()', 'profile_output.txt')
else: 
    app.exec()