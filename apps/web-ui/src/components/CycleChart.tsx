import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { useEffect, useRef } from 'react'
import type { CycleSummary } from '../types'

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

export function CycleChart({ cycles }: { cycles: CycleSummary[] }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current)
    const counts = ['CONFORMING', 'NONCONFORMING', 'UNKNOWN', 'ABORTED'].map(
      (state) => cycles.filter((item) => item.conformance === state).length,
    )
    chart.setOption({
      animationDuration: 250,
      grid: { left: 42, right: 16, top: 16, bottom: 38 },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: ['合规', '不合规', '不可判定', '中止'], axisTick: { show: false } },
      yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#e8ecea' } } },
      series: [{
        type: 'bar', data: counts, barMaxWidth: 42,
        itemStyle: { color: (params: { dataIndex: number }) => ['#2f9d68', '#cf4040', '#d39a21', '#7e8988'][params.dataIndex] },
      }],
    })
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(ref.current)
    return () => { observer.disconnect(); chart.dispose() }
  }, [cycles])
  return <div ref={ref} className="cycle-chart" aria-label="Cycle 结果分布图" />
}
