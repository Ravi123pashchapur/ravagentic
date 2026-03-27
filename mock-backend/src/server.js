const express = require('express');
const cors = require('cors');

const app = express();
const port = Number(process.env.MOCK_BACKEND_PORT || 4000);

const themePayload = {
  theme_name: 'modern-dark',
  palette: ['#111827', '#6366f1', '#f9fafb'],
  style_keywords: ['minimal', 'glassmorphism', 'rounded'],
  layout_preferences: ['dashboard', 'responsive', 'mobile-first']
};

app.use(cors());
app.use(express.json());

app.get('/api/health', (_, res) => {
  res.json({ status: 'ok', service: 'mock-backend' });
});

app.get('/api/theme', (_, res) => {
  res.json(themePayload);
});

app.get('/api/dashboard', (_, res) => {
  res.json({
    cards: [
      { id: 'active_agents', label: 'Active Agents', value: 11 },
      { id: 'quality_score', label: 'Quality Score', value: 90 },
      { id: 'retries', label: 'Retries', value: 0 }
    ]
  });
});

app.listen(port, () => {
  console.log(`mock-backend listening on ${port}`);
});
