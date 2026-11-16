// How a route is written as an SVG path: its corners rounded, its coordinates cut to what a
// drawing needs. The exported drawing and Studio's canvas both draw their wires with it.
import { EDGE_BEND_RADIUS } from '../constants/index.js'
import type { Point, Route } from '../types/index.js'

/** Two decimals is as precise as a coordinate in the drawing ever needs to be. */
export function round(value: number) {
  return Math.round(value * 100) / 100
}

function bend(from: Point, corner: Point, to: Point) {
  const size = Math.min(
    Math.hypot(from.x - corner.x, from.y - corner.y) / 2,
    Math.hypot(corner.x - to.x, corner.y - to.y) / 2,
    EDGE_BEND_RADIUS,
  )
  const { x, y } = corner
  if ((from.x === x && x === to.x) || (from.y === y && y === to.y)) {
    return `L${round(x)} ${round(y)}`
  }
  if (from.y === y) {
    const xDir = from.x < to.x ? -1 : 1
    const yDir = from.y < to.y ? 1 : -1
    return `L ${round(x + size * xDir)},${round(y)}Q ${round(x)},${round(y)} ${round(x)},${round(y + size * yDir)}`
  }
  const xDir = from.x < to.x ? 1 : -1
  const yDir = from.y < to.y ? -1 : 1
  return `L ${round(x)},${round(y + size * yDir)}Q ${round(x)},${round(y)} ${round(x + size * xDir)},${round(y)}`
}

/** The polyline through the points, with a rounded corner wherever it turns. */
export function polylinePath(points: Route) {
  return points
    .map((point, index) => {
      const previous = points[index - 1]
      const next = points[index + 1]
      if (previous && next) return bend(previous, point, next)
      return `${index === 0 ? 'M' : 'L'}${round(point.x)} ${round(point.y)}`
    })
    .join('')
}
