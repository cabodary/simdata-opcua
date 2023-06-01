
import asyncio
from datetime import datetime

from asyncua import ua

from .sim_common import *


async def setup_live_status(stations, nodes, idx, tmc):

	state_nodes = {}
	controlmode_nodes = {}
	downstream_held_nodes = {}

	async def write_state_change(line, obj):
		control_val, state_val = statemap[int(line['Event_Value'])]
		print(f"Writing state change for {obj.name},"
			  f" {obj.state} -> {line['Event_Value']},",
			  f"timestamp={line['Timestamp']} to node {state_nodes[obj.name]}")
		if state_val is not None:
			await state_nodes[obj.name].write_value(ua.Variant(state_val, ua.VariantType.Int32))
		await controlmode_nodes[obj.name].write_value(ua.Variant(control_val, ua.VariantType.Int32))
		if line['Event_Value'] == '2':
			await downstream_held_nodes[obj.name].write_value(True)
		else:
			await downstream_held_nodes[obj.name].write_value(False)

	for name, obj in stations.items():
		livestatus = await nodes[name].get_child(f"{tmc}:LiveStatus")
		state_nodes[name] = await livestatus.get_child(f"{tmc}:State")
		controlmode_nodes[name] = await livestatus.get_child(f"{tmc}:ControlMode")
		downstream_held_nodes[name] = await nodes[name].get_child([f"{tmc}:MaterialOutputPoints",
																   f"{idx}:MaterialOutput",
																   f"{tmc}:DownstreamHeld"])
		obj.on_state_update.append(write_state_change)


async def setup_default_rates(stations, nodes, idx, tmc):
	for name, obj in stations.items():
		output = await nodes[name].get_child([f"{tmc}:MaterialOutputPoints",
											  f"{idx}:MaterialOutput"])
		nominal_rate = await output.get_child(f"{tmc}:NominalProductionRate")
		await nominal_rate.write_value(nominal_rates[name])
		total = await output.get_child(f"{tmc}:ProducedMaterialTotal")
		await total.write_value(20.0 if name=="Oven" else 1.0)


async def setup_output_points(stations, nodes, idx, tmc):

	totals = {}
	sublots = {}
	oven_sublots = []
	oven_properties = []

	def get_sublot(line, obj, properties=True):
		serial = line['Serial_Num']
		part_type = part_types[int(line['Type_ID'])]
		time = datetime.utcnow()
		day = f"{time.year}{time.month:02}{time.day:02}"
		lot_id = f"{day}-{part_type}"

		sublot = ua.MaterialSublotType()
		sublot.ID = f"{lot_id}-{serial}"
		sublot.Quantity = 1.0
		sublot.MaterialLot.ID = lot_id
		sublot.MaterialLot.ProductionDate = time
		sublot.MaterialLot.MaterialDefinition.ID = part_type
		props = []
		if properties:
			props.extend([ua.DataValueType() for _ in range(4)])
			props[0].ID = "process_time"
			props[0].Value = ua.Variant(round(obj.process_time, 4))
			props[1].ID = "part_to_part_time"
			props[1].Value = ua.Variant(round(float(line['Timestamp']) - obj.last_part_out, 4))
			props[2].ID = "reworked"
			props[2].Value = ua.Variant(bool(line['Reworked']))
			props[3].ID = "oven_batch"
			if line['OvenBatch']:
				props[3].Value = ua.Variant(int(line['OvenBatch']))
		sublot.MaterialLot.Properties = props
		sublot.MaterialLot.MaterialDefinition.Properties = []
		sublot.Sublots = []

		return sublot

	async def write_work_out(line, obj):
		sublot = get_sublot(line, obj)
		print(f"Writing part out from {obj.name} - {sublot.ID},",
			  f"timestamp={line['Timestamp']}")
		total = await totals[obj.name].read_value()
		if total is None:
			total = 0.0
		await totals[obj.name].write_value(total + 1.0)
		await sublots[obj.name].write_value(sublot)

	async def oven_work_out(line, obj):
		if (len(oven_sublots) == 0):
			sublot = get_sublot(line, obj)
			oven_properties.extend(sublot.MaterialLot.Properties)
			sublot.MaterialLot.Properties.clear()
			oven_sublots.append(sublot)
		else:
			oven_sublots.append(get_sublot(line, obj, properties=False))

		if (len(oven_sublots) == 20):
			total = await totals[obj.name].read_value()
			if total is None:
				total = 0.0
			await totals[obj.name].write_value(total + 20.0)

			time = datetime.utcnow()
			day = f"{time.year}{time.month:02}{time.day:02}"
			lot_id = f"ovenbatch-{line['OvenBatch']}"
			oven_lot = ua.MaterialSublotType()
			oven_lot.ID = f"{day}-{lot_id}"
			oven_lot.Quantity = 20.0
			oven_lot.MaterialLot.ID = lot_id
			oven_lot.MaterialLot.Properties = oven_properties
			oven_lot.MaterialLot.MaterialDefinition.Properties = []
			oven_lot.Sublots = oven_sublots
			await sublots[obj.name].write_value(oven_lot)

			oven_sublots.clear()
			oven_properties.clear()
			print(f"Writing oven batch out - {lot_id}, timestamp={line['Timestamp']}")

	for name, obj in stations.items():
		output = await nodes[name].get_child([f"{tmc}:MaterialOutputPoints",
											  f"{idx}:MaterialOutput"])
		totals[name] = await output.get_child(f"{tmc}:ProducedMaterialMasterTotal")
		sublots[name] = await output.get_child(f"{tmc}:ProducedMaterial")
		if name == "Oven":
			obj.on_work_out.append(oven_work_out)
		else:
			obj.on_work_out.append(write_work_out)


async def setup_tmc_model(nodes, idx, tmc):
	await setup_live_status(stations, nodes, idx, tmc)
	await setup_default_rates(stations, nodes, idx, tmc)
	await setup_output_points(stations, nodes, idx, tmc)
