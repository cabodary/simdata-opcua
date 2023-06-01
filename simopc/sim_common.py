
from .parse_feed import Activity, Queue


names = (
	"Cleaning",
	"Insulating",
	"Winding 1",
	"Winding 2",
	"Winding 3",
	"Press",
	"Trim and Bind",
	"Oven",
	"Final Inspection",
	"Rework",
	"Queue for Cleaning",
	"Queue for Insulating",
	"Queue for Winding 1",
	"Queue for Press",
	"Queue for Trim and Bind",
	"Queue for Oven",
	"Queue for Final Inspection",
	"Queue for Rework",
)

sim_objects = {} # All objects
stations = {} # Activities only
for name in names:
	if "Queue" in name:
		obj = Queue(name)
		sim_objects[name] = obj
	else:
		obj = Activity(name)
		sim_objects[name] = obj
		stations[name] = obj

part_types = (
	"",
	"BSD12HJ",
	"DWC16JP",
	"SJC19CK",
	"FGC22WS",
	"WSC22PS"
)

# Sim State : (ControlMode, PackML State)
statemap = (
	(1, 12),   # 0 - Starved
	(1, 4),    # 1 - Working
	(1, 12),   # 2 - Blocked
	(4, None), # 3 - Changeover
	(1, 8),    # 4 - Breakdown
	(0, None), # 5 - Off shift
	(1, 15),   # 6 - Resource starved (Staff shortage)
	(2, None)  # 7 - Scheduled maintenance
)

nominal_rates = {		# Parts per hour
	"Cleaning"			: 60.0 * 1  /   4,
	"Insulating"		: 60.0 * 1  /   2,
	"Winding 1"			: 60.0 * 1  /  25,
	"Winding 2"			: 60.0 * 1  /  25,
	"Winding 3"			: 60.0 * 1  /  25,
	"Press"				: 60.0 * 1  /   2,
	"Trim and Bind"		: 60.0 * 1  /   3,
	"Oven"				: 60.0 * 20 / 260,
	"Final Inspection"	: 60.0 * 1  /   2,
	"Rework"			: 60.0 * 1  /  80,
}
