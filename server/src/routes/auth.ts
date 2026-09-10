import { Router } from 'express';
import { lguUsers } from '../data/lguUsers';

const router = Router();

router.post('/login', (req, res) => {
  const { username, password } = req.body ?? {};

  if (!username || !password) {
    return res.status(400).json({ message: 'Username and password are required' });
  }

  const user = lguUsers.find(
    (u) => u.username === username && u.password === password,
  );

  if (!user) {
    return res.status(401).json({ message: 'Invalid username or password' });
  }

  const { password: _password, ...safeUser } = user;
  res.json({ user: safeUser });
});

export default router;
