---
name: Chart Config Generator
description: Map raw JSON datasets into ready-to-use chart configuration objects (Chart.js, Recharts, or ECharts).
metadata:
  source: skills/chart-config-generator/chart-config-generator.md
---

# Chart Config Generator

## Prerequisites & Dependencies
- Node.js 18+ or Python 3.10+ 
- Mandatory packages (choose one):
  - JavaScript: `npm i chart.js`
  - Python: `pip install matplotlib seaborn plotly`
- A raw JSON dataset with numeric values and categorical labels

## Execution Steps
1. Load or define the raw JSON dataset: an array of objects with at least one numeric `value` field and one categorical `label`/`category` field
2. Determine the chart type based on the data shape:
   - Bar chart: compare categories
   - Line chart: show trends over time
   - Pie/Doughnut: show part-to-whole ratios
3. Map dataset fields to chart configuration:
   - X-axis: categorical label field
   - Y-axis: numeric value field
   - Tooltip/custom label: additional fields as needed
4. Generate the chart configuration object:
   - **Chart.js**: `{ type: 'bar', data: { labels: [...], datasets: [{ label: '...', data: [...] }] }, options: { ... } }`
   - **Recharts**: `<BarChart data={...}><Bar dataKey="value" name="..." /></BarChart>`
   - **ECharts**: `option: { xAxis: { data: [...] }, yAxis: { type: 'value' }, series: [{ name: '...', type: 'bar', data: [...] }] }`
5. Customize colors, legends, and responsive settings per the chosen library's API
6. Render the chart in your frontend or export as image/PDF using library-specific methods

```javascript
// Example: Chart.js configuration from raw JSON
const rawData = [
  { category: 'January', value: 65 },
  { category: 'February', value: 59 },
  { category: 'March', value: 80 },
  { category: 'April', value: 81 },
  { category: 'May', value: 56 },
];

const chartConfig = {
  type: 'bar',
  data: {
    labels: rawData.map(item => item.category),
    datasets: [{
      label: 'Sales',
      backgroundColor: 'rgba(54, 162, 235, 0.5)',
      borderColor: 'rgba(54, 162, 235, 1)',
      data: rawData.map(item => item.value),
    }],
  },
  options: {
    responsive: true,
    plugins: {
      legend: { position: 'bottom' },
      title: { display: true, text: 'Monthly Sales' },
    },
    scales: {
      y: { beginAtZero: true },
    },
  },
};

export default chartConfig;
```

```bash
# Render with Chart.js (HTML canvas)
const ctx = document.getElementById('myChart').getContext('2d');
new Chart(ctx, chartConfig);
```
