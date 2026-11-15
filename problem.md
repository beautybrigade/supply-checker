# Problem

Since starting my nail technician journey, I have received many requests for different services. Depending on the service being performed, there are different supplies to be used. Keeping track of the supplies can become a hassle in between appointments, but avoiding running out during a service will help me prevent having to cancel or redo the service.

# Initial requirements

- R1: The program must be able to display a pack size and a unit of measurement for each supply item.
- R2: The program must show stock based on whether the supply comes in packs. If it does, it displays the total packs and loose amount of pieces. If it doesn't, it displays the amount with the item's measurement (gallons, bottles, or another unit).
- R3: The program must be able to restock by pack so I don’t have to do the math of total number of pieces.
- R4: The program must allow each supply item to have its own minimum and let me know when it has fallen below that threshold.
- R5: The program must allow a use command which subtracts what I used during a service and must refuse to go below 0 (example: I can’t use 3 files if I only have 2).
- R6: The program must display a clear error message if the CSV file doesn’t exist, a column is missing, or a quantity isn’t a number. It must also display a clear message if I name a supply item that isn’t in the file.