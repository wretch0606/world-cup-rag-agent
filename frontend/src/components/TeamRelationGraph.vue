<template>
  <aside class="graph-section">
    <h4 class="panel-title">{{ labels.title }}</h4>

    <!-- 加载态 -->
    <div v-if="loading" class="graph-placeholder graph-loading">
      <span class="graph-pulse"></span>
      <p>加载图谱数据...</p>
    </div>

    <!-- 空数据保护 -->
    <div v-else-if="!graphData.nodes.length" class="graph-placeholder graph-empty">
      <span class="graph-empty-icon">📊</span>
      <p>{{ labels.empty }}</p>
    </div>

    <!-- D3 画布 -->
    <div v-else ref="containerRef" class="d3-box"></div>

    <!-- 图例（始终展示） -->
    <div class="graph-legend">
      <h5>{{ labels.legendTitle }}</h5>
      <div class="legend-row"><span class="leg-dot"></span><span>{{ labels.nodeDesc }}</span></div>
      <div class="legend-row"><span class="leg-line"></span><span>{{ labels.edgeDesc }}</span></div>
      <div class="legend-row"><span class="leg-arrow">→</span><span>{{ labels.arrowDesc }}</span></div>
      <div class="legend-fmt">
        <p>{{ labels.edgeFormatDesc }}</p>
        <code>{{ labels.edgeFormatExample }}</code>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount, nextTick } from 'vue'
import * as d3 from 'd3'
import type { GraphData, GraphNode, GraphEdge } from '@/api'

// ============================================================
// Props
// ============================================================
const props = defineProps<{
  graphData: GraphData
  loading?: boolean
}>()

// ============================================================
// 文案
// ============================================================
const labels = {
  title: '球队关系图谱',
  empty: '当前筛选范围暂无图谱数据',
  legendTitle: '图例说明',
  nodeDesc: '节点 = 球队实体',
  edgeDesc: '连线 = 比赛（有向边）',
  arrowDesc: '方向 = 胜方 → 败方',
  edgeFormatDesc: '连线标签格式：',
  edgeFormatExample: '2022·决赛·3:3（点球4:2）',
}

// ============================================================
// D3 状态
// ============================================================
const containerRef = ref<HTMLDivElement | null>(null)
const simulation = ref<d3.Simulation<any, any> | null>(null)

// ============================================================
// D3 初始化（含清理）
// ============================================================
function initD3Graph() {
  // 1. 停止上一次仿真
  if (simulation.value) {
    simulation.value.stop()
    simulation.value = null
  }

  const el = containerRef.value
  if (!el) return

  // 2. 清空旧 SVG
  el.innerHTML = ''

  const nodes: GraphNode[] = props.graphData.nodes
  const edges: GraphEdge[] = props.graphData.edges
  if (!nodes.length) return

  const width = 400
  const height = 280
  const colors = ['#4A90D9', '#E07B39', '#5D9C6E', '#C0504D', '#8064A2', '#F2A640']

  const simNodes: any[] = nodes.map(n => ({ ...n }))
  const simEdges: any[] = edges.map(e => ({ ...e }))

  const svg = d3
    .select(el)
    .append('svg')
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('class', 'd3-svg')
    .attr('width', '100%')
    .attr('height', '100%')

  // 箭头标记
  svg
    .append('defs')
    .append('marker')
    .attr('id', 'ah')
    .attr('viewBox', '0 0 10 7')
    .attr('refX', 10)
    .attr('refY', 3.5)
    .attr('markerWidth', 6)
    .attr('markerHeight', 4)
    .attr('orient', 'auto')
    .append('polygon')
    .attr('points', '0 0,10 3.5,0 7')
    .attr('fill', '#999')

  // 连线
  const link = svg
    .append('g')
    .selectAll('line')
    .data(simEdges)
    .join('line')
    .attr('stroke', '#999')
    .attr('stroke-width', 1.6)
    .attr('marker-end', 'url(#ah)')

  // 节点
  const node = svg
    .append('g')
    .selectAll('circle')
    .data(simNodes)
    .join('circle')
    .attr('r', 26)
    .attr('fill', (_d: any, i: number) => colors[i % 6])
    .attr('opacity', 0.88)
    .attr('stroke', '#fff')
    .attr('stroke-width', 2)

  // 节点标签
  const label = svg
    .append('g')
    .selectAll('text')
    .data(simNodes)
    .join('text')
    .text((d: any) => d.name)
    .attr('text-anchor', 'middle')
    .attr('fill', '#fff')
    .attr('font-size', 13)
    .attr('font-weight', 600)
    .attr('dy', 5)

  // 边标签
  const edgeLabel = svg
    .append('g')
    .selectAll('text')
    .data(simEdges)
    .join('text')
    .text((d: any) => d.label)
    .attr('text-anchor', 'middle')
    .attr('fill', '#333')
    .attr('font-size', 9)
    .attr('font-weight', 600)
    .attr('paint-order', 'stroke')
    .attr('stroke', 'rgba(255,255,255,0.92)')
    .attr('stroke-width', 4)
    .attr('stroke-linecap', 'round')
    .attr('stroke-linejoin', 'round')

  // 3. 创建新仿真
  const sim = d3
    .forceSimulation(simNodes)
    .force(
      'link',
      d3
        .forceLink(simEdges)
        .id((d: any) => d.id)
        .distance(200),
    )
    .force('charge', d3.forceManyBody().strength(-500))
    .force('collide', d3.forceCollide().radius(40))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .on('tick', () => {
      const R = 26
      node
        .attr('cx', (d: any) => {
          d.x = Math.max(R, Math.min(width - R, d.x))
          return d.x
        })
        .attr('cy', (d: any) => {
          d.y = Math.max(R, Math.min(height - R, d.y))
          return d.y
        })

      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y)

      label.attr('x', (d: any) => d.x).attr('y', (d: any) => d.y)

      edgeLabel
        .attr('x', (d: any) => (d.source.x + d.target.x) / 2)
        .attr('y', (d: any) => (d.source.y + d.target.y) / 2 - 8)
    })

  simulation.value = sim
}

// ============================================================
// 响应式 + 清理
// ============================================================
watch(
  () => props.graphData,
  () => nextTick(() => initD3Graph()),
  { deep: true },
)

onBeforeUnmount(() => {
  if (simulation.value) {
    simulation.value.stop()
    simulation.value = null
  }
})
</script>

<style scoped>
.graph-section {
  width: 280px;
  min-width: 280px;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.panel-title {
  margin: 0 0 12px 0;
  font-size: 15px;
  font-weight: 700;
  color: #1a1a1a;
  border-left: 3px solid #4a90d9;
  padding-left: 10px;
}

/* ---- 占位态 ---- */
.graph-placeholder {
  width: 100%;
  height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #fafbfc;
  border: 1px solid #eee;
  border-radius: 6px;
  color: #999;
  font-size: 13px;
  gap: 10px;
}

.graph-empty-icon { font-size: 36px; opacity: 0.6; }

/* 脉冲动画 */
.graph-pulse {
  display: inline-block;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #4a90d9;
  opacity: 0.3;
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(0.8); opacity: 0.3; }
  50% { transform: scale(1.2); opacity: 0.7; }
}

/* ---- D3 画布 ---- */
.d3-box {
  width: 100%;
  height: 280px;
  background: #fafbfc;
  border: 1px solid #eee;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

:deep(.d3-svg) { width: 100%; height: 280px; }
:deep(.d3-svg text) { text-shadow: 1px 1px 2px #fff, -1px -1px 2px #fff; }

/* ---- 图例 ---- */
.graph-legend {
  margin-top: 12px;
  padding: 12px;
  background: #f9fafb;
  border-radius: 6px;
  font-size: 12px;
}

.graph-legend h5 {
  margin: 0 0 8px 0;
  font-size: 13px;
  font-weight: 700;
  color: #555;
}

.legend-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  color: #666;
}

.leg-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  background: #4a90d9;
  border-radius: 50%;
  flex-shrink: 0;
}

.leg-line {
  display: inline-block;
  width: 20px;
  height: 2px;
  background: #999;
  flex-shrink: 0;
}

.leg-arrow {
  flex-shrink: 0;
  color: #999;
}

.legend-fmt {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #eee;
}

.legend-fmt p {
  margin: 0 0 4px 0;
  color: #888;
}

.legend-fmt code {
  display: block;
  font-size: 11px;
  color: #4a90d9;
  background: #e8f0fe;
  padding: 3px 6px;
  border-radius: 4px;
  word-break: break-all;
}
</style>
