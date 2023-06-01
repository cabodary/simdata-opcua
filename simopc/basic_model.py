
import asyncio
from datetime import datetime

from asyncua import ua

from .sim_common import *


async def setup_live_status(stations, nodes, idx):

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
		livestatus = await nodes[name].get_child(f"{idx}:LiveStatus")
		state_nodes[name] = await livestatus.get_child(f"{idx}:State")
		controlmode_nodes[name] = await livestatus.get_child(f"{idx}:ControlMode")
		downstream_held_nodes[name] = await nodes[name].get_child([f"{idx}:OutputPoint",
																   f"{idx}:DownstreamHeld"])
		obj.on_state_update.append(write_state_change)


async def setup_default_rates(stations, nodes, idx):
	for name, obj in stations.items():
		output = await nodes[name].get_child(f"{idx}:OutputPoint")
		nominal_rate = await output.get_child(f"{idx}:NominalProductionRate")
		await nominal_rate.write_value(nominal_rates[name])
		quantity = await output.get_child([f"{idx}:ProducedMaterial",
										   f"{idx}:Quantity"])
		await quantity.write_value(20.0 if name=="Oven" else 1.0)
		total = await output.get_child(f"{idx}:ProducedMaterialTotal")
		await total.write_value(20.0 if name=="Oven" else 1.0)


async def get_property_nodes(lot_node, idx):
	properties = await lot_node.get_child(f"{idx}:Properties")
	process_time = await properties.get_child(f"{idx}:ProcessTime")
	p2p_time = await properties.get_child(f"{idx}:PartToPartTime")
	reworked = await properties.get_child(f"{idx}:Reworked")
	ovenbatch = await properties.get_child(f"{idx}:OvenBatch")
	return (process_time, p2p_time, reworked, ovenbatch)


async def write_lot_properties(line, obj, prop_nodes):
	process_time, p2p_time, reworked, ovenbatch = prop_nodes
	await asyncio.gather(
		process_time.write_value(round(obj.process_time, 5)),
		p2p_time.write_value(round(float(line['Timestamp']) - obj.last_part_out, 5)),
		reworked.write_value(bool(line['Reworked']))
	)

	batch_id = line['OvenBatch']
	if batch_id:
		await ovenbatch.write_value(ua.Variant(int(batch_id),
									ua.VariantType.Int32))


async def setup_output_points(stations, nodes, idx):

	totals = {}
	lot_ids = {}
	material_ids = {}
	dates = {}

	property_tups = {}

	async def write_work_out(line, obj):
		serial = line['Serial_Num']
		part_type = part_types[int(line['Type_ID'])]
		time = datetime.utcnow()
		day = f"{time.year}{time.month:02}{time.day:02}"
		lot_id = f"{day}-{part_type}-{serial}"
		total = await totals[obj.name].read_value()
		if total is None:
			total = 0.0

		print(f"Writing part out from {obj.name} - {lot_id}")

		await asyncio.gather(
			totals[obj.name].write_value(total + 1.0),
			lot_ids[obj.name].write_value(lot_id),
			material_ids[obj.name].write_value(part_type),
			dates[obj.name].write_value(time))
		await write_lot_properties(line, obj, property_tups[obj.name])

	for name, obj in stations.items():
		output = await nodes[name].get_child(f"{idx}:OutputPoint")
		totals[obj.name] = await output.get_child(f"{idx}:ProducedMaterialMasterTotal")

		material = await output.get_child(f"{idx}:ProducedMaterial")
		lot_ids[obj.name] = await material.get_child(f"{idx}:LotID")
		dates[obj.name] = await material.get_child(f"{idx}:ProductionDate")
		material_ids[obj.name] = await material.get_child([f"{idx}:MaterialDefinition",
														   f"{idx}:MaterialID"])

		property_tups[obj.name] = await get_property_nodes(material, idx)

		obj.on_work_out.append(write_work_out)


async def setup_oven(oven_obj, oven_node, idx):

	track = {
		"oven_idx": 0
	}

	output = await oven_node.get_child(f"{idx}:OutputPoint")
	total_node = await output.get_child(f"{idx}:ProducedMaterialMasterTotal")
	ovenlot_node = await output.get_child(f"{idx}:ProducedMaterial")
	lot_id_node = await ovenlot_node.get_child(f"{idx}:LotID")
	date_node = await ovenlot_node.get_child(f"{idx}:ProductionDate")
	property_nodes = await get_property_nodes(ovenlot_node, idx)

	sublots_node = await ovenlot_node.get_child(f"{idx}:Sublots")
	sublot_tups = []
	for i in range(20):
		sublot = await sublots_node.get_child(f"{idx}:Part{i+1:02}")
		sublot_id = await sublot.get_child(f"{idx}:LotID")
		sublot_date = await sublot.get_child(f"{idx}:ProductionDate")
		mat_id = await sublot.get_child([f"{idx}:MaterialDefinition",
										 f"{idx}:MaterialID"])
		sublot_tups.append((sublot_id, sublot_date, mat_id))
		await (await sublot.get_child(f"{idx}:Quantity")).write_value(1.0)
	await (await ovenlot_node.get_child(f"{idx}:Quantity")).write_value(20.0)

	async def oven_work_out(line, obj):
		serial = line['Serial_Num']
		part_type = part_types[int(line['Type_ID'])]
		time = datetime.utcnow()
		day = f"{time.year}{time.month:02}{time.day:02}"
		sublot_id = f"{day}-{part_type}-{serial}"
		total = await total_node.read_value()
		if total is None:
			total = 0.0
		oven_idx = track['oven_idx']
		print(f"Writing part out from Oven - {sublot_id} - {oven_idx}")

		# Write to one of the sublot objects
		sublot_id_node, sublot_date, mat_id = sublot_tups[oven_idx]
		await asyncio.gather(
			sublot_id_node.write_value(sublot_id),
			mat_id.write_value(part_type),
			sublot_date.write_value(time),
		)

		# Once per batch, write to the lot object
		if oven_idx == 0:
			ovenlot_id = f"{day}-ovenbatch-{line['OvenBatch']}"
			await asyncio.gather(
				total_node.write_value(total + 20.0),
				lot_id_node.write_value(ovenlot_id),
				write_lot_properties(line, obj, property_nodes),
				date_node.write_value(time))

		track['oven_idx'] = (oven_idx + 1) % 20

	oven_obj.on_work_out.append(oven_work_out)


async def setup_basic_model(nodes, idx):
	non_oven_stations = {k: v for k, v in stations.items() if k != "Oven"}
	await asyncio.gather(
		setup_live_status(stations, nodes, idx),
		setup_default_rates(stations, nodes, idx),
		setup_output_points(non_oven_stations, nodes, idx),
		setup_oven(stations['Oven'], nodes['Oven'], idx))
