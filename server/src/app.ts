import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import { PestRecord } from '@rice-pest/shared-types';
import authRouter from './routes/auth';
import weatherRouter from './routes/weather';

const app = express();
app.use(cors());
app.use(express.json());

app.get('/api/health', (req, res) => {
  res.json({ status: 'Server is running smoothly' });
});

app.use('/api/auth', authRouter);
app.use('/api/weather', weatherRouter);

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
  console.log(`Backend server running on port ${PORT}`);
});