
import csv, asyncio


class Queue:
	def __init__(self, name):
		self.name = name
		self.parts = []
		self.on_work_in = []
		self.on_work_out = []

	async def work_in(self, line):
		self.parts.append(line)
		for func in self.on_work_in:
			if asyncio.iscoroutinefunction(func):
				await func(line, self)
			else:
				func(line, self)

	async def work_out(self, line):
		for i, part in enumerate(self.parts):
			if part['Serial_Num'] == line['Serial_Num']:
				del self.parts[i]
		for func in self.on_work_out:
			if asyncio.iscoroutinefunction(func):
				await func(line, self)
			else:
				func(line, self)


class Activity:
	def __init__(self, name):
		self.name = name
		self.state = 0
		self.last_timestamp = 0
		self.last_part_out = 0
		self.process_time = 0.0
		self.on_work_in = []
		self.on_work_out = []
		self.on_state_update = []

	async def work_in(self, line):
		for func in self.on_work_in:
			if asyncio.iscoroutinefunction(func):
				await func(line, self)
			else:
				func(line, self)
		self.last_timestamp = float(line['Timestamp'])

	async def work_out(self, line):
		timestamp = float(line['Timestamp'])
		if self.state in {1, '1'}:
			self.process_time += timestamp - self.last_timestamp
		for func in self.on_work_out:
			if asyncio.iscoroutinefunction(func):
				await func(line, self)
			else:
				func(line, self)
		self.process_time = 0.0
		self.last_part_out = timestamp
		self.last_timestamp = timestamp

	async def state_update(self, line):
		timestamp = float(line['Timestamp'])
		if self.state in {1, '1'}:
			self.process_time += timestamp - self.last_timestamp
		for func in self.on_state_update:
			if asyncio.iscoroutinefunction(func):
				await func(line, self)
			else:
				func(line, self)
		self.state = line['Event_Value']
		self.last_timestamp = timestamp


async def process_event(event_lines, objects):
	state_changes = {}
	for line in event_lines:
		name = line['Object']
		if line['Event_Name'] == "State":
			state_changes[name] = line
		elif line['Event_Name'] == "Work_In":
			if name in objects:
				await objects[name].work_in(line)
		elif line['Event_Name'] == "Work_Out":
			if name in objects:
				await objects[name].work_out(line)
	for name, line in state_changes.items():
		if name in objects:
			await objects[name].state_update(line)


async def parse_feed(reader, objects={}, wait=0, start=0, add_untracked_objects=False):
	"""
	reader = csv.Dictreader object
	objects = dict of {name: Activity/Queue object}
	wait = seconds to wait per timestamp unit
	start = starting timestamp to fast forward to
	"""
	line = next(reader)
	while not line['Timestamp']:
		line = next(reader)
	timestamp = line['Timestamp']
	last_event_time = 0.0
	event_lines = [line]
	fast_forward = True
	for line in reader:
		if not line['Timestamp']:
			continue

		if add_untracked_objects:
			name = line['Object']
			if name not in objects:
				objects[name] = Queue(name) if "Queue" in name else Activity(name)

		if line['Timestamp'] == timestamp:
			event_lines.append(line)
		else:
			event_time = float(timestamp)
			if fast_forward:
				if event_time > start:
					fast_forward = False
					last_event_time = event_time
					sleeptime = event_time - start
					await asyncio.sleep(wait * sleeptime)
				await process_event(event_lines, objects)
			else:
				sleeptime = event_time - last_event_time
				await asyncio.sleep(wait * sleeptime)
				await process_event(event_lines, objects)
				last_event_time = event_time
			event_lines = [line]
			timestamp = line['Timestamp']

	if event_lines:
		await process_event(event_lines, objects)

	return objects


if __name__ == "__main__":

	with open("../data/schedule1.csv", 'r') as f:
		reader = csv.DictReader(f)
		objects = asyncio.run(parse_feed(reader, add_untracked_objects=True))
		for key in objects:
			print(key)

