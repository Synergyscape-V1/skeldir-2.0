import type { PlatformType } from "../../types/channel";
import { platformMeta } from "../core/constants";

interface ChannelIconProps {
  platformType: PlatformType;
  size?: number;
}

export function ChannelIcon({ platformType, size = 24 }: ChannelIconProps) {
  const meta = platformMeta(platformType);
  return <img src={meta.iconSrc} alt={meta.label} width={size} height={size} style={{ display: "block" }} />;
}
