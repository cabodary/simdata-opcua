
import asyncio, configparser, argparse, csv

from asyncua import Server, Client
from asyncua.common.structures104 import load_enums, load_custom_struct

from simopc import parse_feed, stations, setup_basic_model, setup_tmc_model


async def main(args, usage):

	setup = args.preset
	config = configparser.ConfigParser()
	defaults = {
		'write_as_client':		"False",
		'server_name':			"Python Sim",
		'endpoint':				"",
		'use_tmc':				"False",
		'feed_filepath':		"data/schedule1.csv",
		'playback_speed':		"1",
		'skip_to_time':			"0",
		'start_timestamp':		"365",
	}
	restored_config = False
	altered_defaults = False
	if not config.read('presets.cfg'):
		restore_config(config, defaults)
		restored_config = True
	elif config['DEFAULT'] != defaults:
		if not config['DEFAULT'].keys():
			restore_config(config, defaults)
			restored_config = True
		else:
			config['DEFAULT'] = defaults | dict(config['DEFAULT'])
			altered_defaults = True

	if setup not in config:
		setup = setup.lower()
		if setup not in config:
			setup = setup.upper()
			if setup not in config:
				for preset in config:
					if setup == preset.upper():
						setup = preset
				if setup not in config:
					print(usage)
					print(f"Preset '{args.preset}' not found: check presets.cfg")
					return 1

	hosting = False if args.client else not config[setup].getboolean('write_as_client')
	use_tmc = True if args.tmc_model else config[setup].getboolean('use_tmc')
	endpoint = args.endpoint if args.endpoint else config[setup]['endpoint']
	feed_file = args.feed_file if args.feed_file else config[setup]['feed_filepath']
	speed = float(args.speed) if args.speed else config[setup].getfloat('playback_speed')
	speed = 60 / speed if speed > 0 else 0
	skip_to = float(args.skip) if args.skip else config[setup].getfloat('skip_to_time')
	fast_forward_to = float(args.start) if args.start else config[setup].getfloat('start_timestamp')

	if not endpoint:
		print(usage)
		print("No endpoint specified, use -e ENDPOINT or 'endpoint = ENDPOINT' in presets.cfg\n")
		return 2

	if altered_defaults:
		print(f"WARNING: Preset defaults have been altered, delete [DEFAULT] section to restore")

	if hosting:
		server = Server()
		await server.init()
		server.set_server_name("Python Sim")
		server.set_endpoint(endpoint)

		if use_tmc:
			await server.import_xml("nodesets/DI.xml")
			await server.import_xml("nodesets/PackML.xml")
			await server.import_xml("nodesets/TMC.xml")
		else:
			await server.import_xml("nodesets/simbasic.xml")
		session = server

	else:
		session = Client(endpoint)

	async with session:
		if (use_tmc):
			tmc = await session.get_namespace_index("http://opcfoundation.org/UA/TMC/v2/")
			idx = await session.get_namespace_index("http://sandhillconsulting.net/UA/SimInstances/")
			await load_enums(session)
			await load_custom_struct(session.get_node(f"ns={tmc};i=3019")) # DataDescriptionType
			await load_custom_struct(session.get_node(f"ns={tmc};i=3011")) # DataValueType
			await load_custom_struct(session.get_node(f"ns={tmc};i=3010")) # MaterialDefinitionType
			await load_custom_struct(session.get_node(f"ns={tmc};i=3012")) # MaterialLotType
			await load_custom_struct(session.get_node(f"ns={tmc};i=3025")) # MaterialSublotType
		else:
			idx = await session.get_namespace_index("http://sandhillconsulting.net/UA/SimBasic/")

		assembly = await session.nodes.objects.get_child(f"{idx}:AssemblyLine")
		nodes = {name: await assembly.get_child(f"{idx}:{name}")
				 for name in stations}

		if (use_tmc):
			await setup_tmc_model(nodes, idx, tmc)
		else:
			await setup_basic_model(nodes, idx)

		with open(feed_file, 'r') as f:
			fieldnames = f.readline().rstrip().split(',')

			# Start playback from the given timestamp
			if skip_to > 0:
				pos = f.tell()
				time_idx = fieldnames.index('Timestamp')
				while line := f.readline().split(','):
					if line[time_idx] and float(line[time_idx]) >= skip_to:
						f.seek(pos)
						break
					pos = f.tell()

			reader = csv.DictReader(f, fieldnames)

			message = f"Beginning {'TMC ' if use_tmc else ''}playback "
			message += f"with events from t={skip_to} -> t={fast_forward_to}"
			if speed != 60.0:
				message += f" at {speed} seconds per timestamp unit"
			print(f"{message}...\n")
			await asyncio.sleep(5)

			await parse_feed(reader, stations, wait=speed, start=fast_forward_to)
			print("End of data feed")
			while True:
				await asyncio.sleep(1)


def restore_config(config, defaults):

	config['DEFAULT'] = defaults

	if 'basic' not in config:
		config['basic'] = {}
		config['basic']['server_name']		= "Python Sim"
		config['basic']['endpoint']			= "opc.tcp://0.0.0.0:4840/freeopcua/server/"

	if 'basic_client' not in config:
		config['basic_client'] = {}
		config['basic_client']['write_as_client']	= "True"
		config['basic_client']['endpoint']			= "opc.tcp://localhost:53530/OPCUA/SimulationServer"

	if 'tmc_client' not in config:
		config['tmc_client'] = {}
		config['tmc_client']['use_tmc']			= "True"
		config['tmc_client']['write_as_client']	= "True"
		config['tmc_client']['endpoint']		= "opc.tcp://localhost:53530/OPCUA/SimulationServer"

	if 'testing' not in config:
		config['testing'] = {}
		config['testing']['server_name']	= "Python Sim Testing"
		config['testing']['endpoint']		= "opc.tcp://localhost:53530/OPCUA/SimulationServer"
		config['testing']['playback_speed']	= "60"

	with open("presets.cfg", 'w') as configfile:
		config.write(configfile)


def parse_arguments():
	parser = argparse.ArgumentParser(description="Provides live OPC UA data "
									 "from a CSV feed of simulated factory events")
	parser.add_argument("-p", metavar="PRESET", dest="preset",
						help="Name of base configuration preset to use from presets.cfg",
						default="DEFAULT")
	parser.add_argument("-t", "--tmc_model", action="store_true",
						help="Use the TMC-based model instead of the basic model")
	parser.add_argument("-c", "--client", action="store_true",
						help="Write the data to a separate server as a Python client")
	parser.add_argument("-e", metavar="ENDPOINT", dest="endpoint",
						help="Endpoint to host / Endpoint to target as client")
	parser.add_argument("-n", metavar="NAME", dest="server_name",
						help="Name to use for Python server (if hosting)")
	parser.add_argument("-f", metavar="FEED_FILE", dest="feed_file",
						help="Filename of CSV with simulation data")
	parser.add_argument("-s", metavar="TIMESTAMP", dest="skip",
						help="Skip to given time in feed file before writing anything")
	parser.add_argument("-b", metavar="TIMESTAMP", dest="start",
						help="Begin live playback by fast-forwarding to given time")
	parser.add_argument("-x", metavar="SPEED", dest="speed",
						help="Playback speed multiplier")
	args = parser.parse_args()
	return args, parser.format_help()


if __name__ == "__main__":
	args, usage = parse_arguments()
	asyncio.run(main(args, usage))
