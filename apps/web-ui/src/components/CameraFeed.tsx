import type { StationSnapshot } from '../types'
import { SimulatedFeed } from './SimulatedFeed'

interface Props {
  snapshot: StationSnapshot
}

export function CameraFeed({ snapshot }: Props) {
  const { video } = snapshot
  if (video.kind === 'USB_MJPEG' && video.stream_url) {
    return <img className="usb-camera-feed" src={video.stream_url} alt="" aria-label="ST01 USB 摄像头画面" />
  }
  return <SimulatedFeed snapshot={snapshot} />
}
