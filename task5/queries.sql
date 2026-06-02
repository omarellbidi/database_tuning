-- option a;
SELECT balance
INTO e
FROM Accounts
WHERE account = i;

UPDATE Accounts
SET balance = e + 1
WHERE account = i;

SELECT balance
INTO c
FROM Accounts
WHERE account = 0;

UPDATE Accounts
SET balance = c - 1
WHERE account = 0;

-- option b; 
UPDATE Accounts SET balance=balance+1 WHERE account=i;
UPDATE Accounts SET balance=balance-1 WHERE account=0;