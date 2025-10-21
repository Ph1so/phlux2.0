import csv

names = []
with open('companies.csv', 'r') as file:
    reader = csv.DictReader(file)  # reads rows as dictionaries
    for row in reader:
        names.append(row['Name'])  # 'Name' is the column header

print(names)
