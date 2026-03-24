import React, { useEffect, useMemo, useRef, useState } from "react";
import { CHANNEL_COLORS, displayChannelName, platformMeta } from "../core/constants";
import type { AvailableChannel } from "../../types/comparison";

interface ChannelSelectorProps {
  availableChannels: AvailableChannel[];
  selectedChannelIds: string[];
  onAddChannel: (channelId: string) => void;
  onAddManualChannel: (channelId: string) => void;
  onRemoveChannel: (channelId: string) => void;
  maxChannels?: number;
}

export function ChannelSelector({
  availableChannels,
  selectedChannelIds,
  onAddChannel,
  onAddManualChannel,
  onRemoveChannel,
  maxChannels = 4,
}: ChannelSelectorProps) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [manualValue, setManualValue] = useState("");
  const rootRef = useRef<HTMLDivElement | null>(null);

  const selectedMap = useMemo(
    () => new Map(availableChannels.map((channel) => [channel.id, channel])),
    [availableChannels]
  );
  const remainingChannels = useMemo(
    () => availableChannels.filter((channel) => !selectedChannelIds.includes(channel.id)),
    [availableChannels, selectedChannelIds]
  );

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, []);

  useEffect(() => {
    if (activeIndex > remainingChannels.length - 1) {
      setActiveIndex(Math.max(remainingChannels.length - 1, 0));
    }
  }, [activeIndex, remainingChannels.length]);

  const disabled = selectedChannelIds.length >= maxChannels;

  return (
    <section className="cc-selector-wrap">
      <div className="cc-selector-row">
        <div className="cc-selector-combobox" ref={rootRef}>
          <button
            type="button"
            role="combobox"
            aria-expanded={open}
            aria-haspopup="listbox"
            aria-controls="cc-channel-listbox"
            className="cc-selector-trigger"
            disabled={disabled}
            onClick={() => {
              setOpen((value) => !value);
            }}
            onKeyDown={(event) => {
              if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
                event.preventDefault();
                setOpen(true);
                return;
              }
              if (!open) return;
              if (event.key === "Escape") {
                setOpen(false);
                return;
              }
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setActiveIndex((index) => Math.min(index + 1, remainingChannels.length - 1));
                return;
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setActiveIndex((index) => Math.max(index - 1, 0));
                return;
              }
              if (event.key === "Enter") {
                event.preventDefault();
                const option = remainingChannels[activeIndex];
                if (!option) return;
                onAddChannel(option.id);
                setOpen(false);
              }
            }}
          >
            + Add Channel
          </button>

          {open ? (
            <ul id="cc-channel-listbox" role="listbox" className="cc-selector-listbox" aria-label="Available channels">
              {remainingChannels.length === 0 ? (
                <li className="cc-selector-option-empty">No channels remaining</li>
              ) : (
                remainingChannels.map((channel, index) => {
                  const meta = platformMeta(channel.platform_type);
                  const isActive = index === activeIndex;
                  return (
                    <li
                      key={channel.id}
                      role="option"
                      aria-selected={isActive}
                      className={`cc-selector-option${isActive ? " is-active" : ""}`}
                      onMouseEnter={() => setActiveIndex(index)}
                      onClick={() => {
                        onAddChannel(channel.id);
                        setOpen(false);
                      }}
                    >
                      <img src={meta.iconSrc} alt={meta.label} width={20} height={20} />
                      <span>{displayChannelName(channel.name, channel.platform_type)}</span>
                    </li>
                  );
                })
              )}
            </ul>
          ) : null}
        </div>

        {selectedChannelIds.map((id, index) => {
          const channel = selectedMap.get(id);
          const color = CHANNEL_COLORS[index] ?? CHANNEL_COLORS[0];
          const meta = channel ? platformMeta(channel.platform_type) : null;
          const name = channel ? displayChannelName(channel.name, channel.platform_type) : id;
          return (
            <div
              key={id}
              className="cc-selector-chip"
              role="group"
              aria-label={`${name} comparison panel`}
              style={
                {
                  "--chip-color": color,
                } as React.CSSProperties
              }
            >
              {meta ? <img src={meta.iconSrc} alt={meta.label} width={20} height={20} /> : null}
              <span>{name}</span>
              <button type="button" aria-label={`Remove ${name} from comparison`} onClick={() => onRemoveChannel(id)}>
                x
              </button>
            </div>
          );
        })}
      </div>

      {availableChannels.length === 0 ? (
        <div className="cc-manual-add-row">
          <label htmlFor="cc-manual-channel">Manual channel id</label>
          <div>
            <input
              id="cc-manual-channel"
              type="text"
              value={manualValue}
              onChange={(event) => setManualValue(event.target.value)}
              placeholder="e.g. ch_google_ads"
            />
            <button
              type="button"
              onClick={() => {
                onAddManualChannel(manualValue);
                setManualValue("");
              }}
              disabled={manualValue.trim().length === 0 || disabled}
            >
              Add
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
