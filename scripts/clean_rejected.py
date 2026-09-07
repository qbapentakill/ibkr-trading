import sqlite3
conn = sqlite3.connect('data/trading.db')
cur = conn.cursor()
cur.execute("DELETE FROM orders WHERE status='rejected'")
conn.commit()
print(f'Usunieto {cur.rowcount} odrzuconych zlecen')
conn.close()
