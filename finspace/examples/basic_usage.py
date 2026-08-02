from finspace import Space

space = Space.load("examples/european_options.yaml")
print(space.describe())

rank, record = space.sample(1, seed=42, with_ranks=True)[0]
print("rank", rank)
print("record", record)
assert space.unrank(rank) == record

for partition in space.partitions(4):
    print(partition.to_dict())
