
Python script for live playback of simulated factory event data
through OPC UA, operating as either a server or a client.

Requires opcua-asyncio (https://github.com/FreeOpcUa/opcua-asyncio)

	pip install asyncua

## Usage

	usage: run_sim.py [-h] [-p PRESET] [-t] [-c] [-e ENDPOINT] [-n NAME]
	                  [-f FEED_FILE] [-s TIMESTAMP] [-b TIMESTAMP] [-x SPEED]

	Provides live OPC UA data from a CSV feed of simulated factory events

	options:
	  -h, --help       show this help message and exit
	  -p PRESET        Name of base configuration preset to use from presets.cfg

	override preset:
	  -t, --tmc_model  Use the TMC-based model instead of the basic model
	  -c, --client     Write the data to a separate server as a Python client
	  -e ENDPOINT      Endpoint to host / Endpoint to target as client
	  -n NAME          Name to use for Python server (if hosting)
	  -f FEED_FILE     Filename of CSV with simulation data
	  -s TIMESTAMP     Skip to given time in feed file before writing anything
	  -b TIMESTAMP     Begin live playback by fast-forwarding to given time
	  -x SPEED         Playback speed multiplier

## Configuration Presets

Can be added/edited in `presets.cfg`, determines the base settings for how to write the data and where to write it to.

	[basic]
	server_name = Python Sim
	endpoint = opc.tcp://0.0.0.0:4840/freeopcua/server/

	[basic_client]
	write_as_client = True
	endpoint = opc.tcp://localhost:53530/OPCUA/SimulationServer

	[tmc_client]
	use_tmc = True
	write_as_client = True
	endpoint = opc.tcp://localhost:53530/OPCUA/SimulationServer

## OPC UA Nodesets

The simulation can write to one of two information models:
* One leveraging the TMC companion spec (https://github.com/OPCFoundation/UA-Nodeset/tree/latest/TMC)
* A more basic nodeset mirroring the TMC structure using base OPC data types

If using a separate OPC UA server, import the instance nodeset for the desired
information model, which will add a folder of `AssemblyLine` stations to
`Objects` corresponding to the data feed: 
* Basic model types + instances - `nodesets/SimBasic.xml`
* TMC instances - `nodesets/SimInstancesTMC.xml`

If using the TMC-based model, the required companion nodesets are also included:
* DI 1.03.0 - `nodesets/DI.xml`
* PackML 1.01 - `nodesets/PackML.xml`
* TMC v2 2.00.1 - `nodesets/TMC.xml`
