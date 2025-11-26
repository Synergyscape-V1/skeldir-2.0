import * as React from "react"
import {
  useFloating,
  autoUpdate,
  offset,
  flip,
  shift,
  useHover,
  useFocus,
  useDismiss,
  useRole,
  useInteractions,
  FloatingPortal,
  arrow,
  FloatingArrow,
  type Placement,
  type Middleware,
} from "@floating-ui/react"
import { cn } from "@/lib/utils"

interface TooltipContextValue {
  open: boolean
  setOpen: (open: boolean) => void
  getReferenceProps: (userProps?: React.HTMLProps<Element>) => Record<string, unknown>
  getFloatingProps: (userProps?: React.HTMLProps<HTMLElement>) => Record<string, unknown>
  refs: {
    reference: React.MutableRefObject<any>
    floating: React.MutableRefObject<any>
    setReference: (node: any) => void
    setFloating: (node: any) => void
  }
  floatingStyles: React.CSSProperties
  arrowRef: React.MutableRefObject<SVGSVGElement | null>
  placement: Placement
  context: any
}

const TooltipContext = React.createContext<TooltipContextValue | null>(null)

const useTooltipContext = () => {
  const context = React.useContext(TooltipContext)
  if (!context) {
    throw new Error("Tooltip components must be wrapped in <TooltipAdvanced />")
  }
  return context
}

interface TooltipAdvancedProps {
  children: React.ReactNode
  placement?: Placement
  sideOffset?: number
  collisionPadding?: number
  protectedElements?: string[]
  onOpenChange?: (open: boolean) => void
}

export function TooltipAdvanced({
  children,
  placement = "top",
  sideOffset = 8,
  collisionPadding = 16,
  protectedElements = [],
  onOpenChange,
}: TooltipAdvancedProps) {
  const [open, setOpen] = React.useState(false)
  const arrowRef = React.useRef<SVGSVGElement>(null)

  const detectProtectedElementCollision = React.useCallback(
    (state: any): Middleware => {
      return {
        name: "detectProtectedElementCollision",
        async fn(middlewareState) {
          const { x, y, elements, rects } = middlewareState

          if (!elements.floating || protectedElements.length === 0) {
            return { x, y }
          }

          const floatingRect = elements.floating.getBoundingClientRect()
          const tooltipBounds = {
            top: y,
            left: x,
            right: x + rects.floating.width,
            bottom: y + rects.floating.height,
          }

          for (const selector of protectedElements) {
            const protectedElement = document.querySelector(selector)
            if (!protectedElement) continue

            const protectedRect = protectedElement.getBoundingClientRect()

            const hasCollision =
              tooltipBounds.left < protectedRect.right &&
              tooltipBounds.right > protectedRect.left &&
              tooltipBounds.top < protectedRect.bottom &&
              tooltipBounds.bottom > protectedRect.top

            if (hasCollision) {
              const availableAbove = protectedRect.top - rects.floating.height - sideOffset
              const availableBelow = window.innerHeight - protectedRect.bottom - rects.floating.height - sideOffset
              const availableLeft = protectedRect.left - rects.floating.width - sideOffset
              const availableRight = window.innerWidth - protectedRect.right - rects.floating.width - sideOffset

              const spaces = [
                { space: availableAbove, placement: "top" as Placement },
                { space: availableBelow, placement: "bottom" as Placement },
                { space: availableLeft, placement: "left" as Placement },
                { space: availableRight, placement: "right" as Placement },
              ]

              const bestSpace = spaces.reduce((max, current) => 
                current.space > max.space ? current : max
              )

              if (bestSpace.space > 0) {
                return {
                  x,
                  y,
                  reset: {
                    placement: bestSpace.placement,
                  },
                }
              }
            }
          }

          return { x, y }
        },
      }
    },
    [protectedElements, sideOffset]
  )

  const middleware: Middleware[] = [
    offset(sideOffset),
    flip({
      fallbackAxisSideDirection: "start",
      padding: collisionPadding,
      crossAxis: true,
    }),
    shift({
      padding: collisionPadding,
    }),
    detectProtectedElementCollision({}),
    arrow({
      element: arrowRef,
      padding: 8,
    }),
  ]

  const { refs, floatingStyles, context, placement: computedPlacement } = useFloating({
    open,
    onOpenChange: (newOpen) => {
      setOpen(newOpen)
      onOpenChange?.(newOpen)
    },
    placement,
    middleware,
    whileElementsMounted: autoUpdate,
  })

  const hover = useHover(context, {
    delay: { open: 100, close: 0 },
    move: false,
  })
  const focus = useFocus(context)
  const dismiss = useDismiss(context)
  const role = useRole(context, { role: "tooltip" })

  const { getReferenceProps, getFloatingProps } = useInteractions([
    hover,
    focus,
    dismiss,
    role,
  ])

  return (
    <TooltipContext.Provider
      value={{
        open,
        setOpen,
        getReferenceProps,
        getFloatingProps,
        refs,
        floatingStyles,
        arrowRef,
        placement: computedPlacement,
        context,
      }}
    >
      {children}
    </TooltipContext.Provider>
  )
}

export const TooltipAdvancedTrigger = React.forwardRef<
  HTMLElement,
  React.HTMLAttributes<HTMLElement> & { asChild?: boolean }
>(({ children, asChild = false, ...props }, propRef) => {
  const context = useTooltipContext()

  const childrenRef = (children as any).ref
  const ref = React.useMemo(
    () => {
      if (propRef == null && childrenRef == null) {
        return context.refs.setReference
      }

      return (node: any) => {
        context.refs.setReference(node)

        if (typeof propRef === "function") {
          propRef(node)
        } else if (propRef) {
          propRef.current = node
        }

        if (typeof childrenRef === "function") {
          childrenRef(node)
        } else if (childrenRef) {
          childrenRef.current = node
        }
      }
    },
    [context.refs.setReference, propRef, childrenRef]
  )

  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(
      children,
      context.getReferenceProps({
        ref,
        ...props,
        ...children.props,
      })
    )
  }

  return (
    <button
      ref={ref}
      type="button"
      data-state={context.open ? "open" : "closed"}
      {...context.getReferenceProps(props)}
    >
      {children}
    </button>
  )
})
TooltipAdvancedTrigger.displayName = "TooltipAdvancedTrigger"

export const TooltipAdvancedContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { showArrow?: boolean }
>(({ className, children, showArrow = true, ...props }, propRef) => {
  const context = useTooltipContext()

  if (!context.open) return null

  return (
    <FloatingPortal>
      <div
        ref={context.refs.setFloating}
        style={context.floatingStyles}
        {...context.getFloatingProps(props)}
        className={cn(
          "z-50 overflow-hidden rounded-md glass-tooltip px-3 py-2.5 text-sm",
          "animate-in fade-in-0 zoom-in-95",
          "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
          className
        )}
        data-state={context.open ? "open" : "closed"}
        data-placement={context.placement}
      >
        {children}
        {showArrow && (
          <FloatingArrow
            ref={context.arrowRef}
            context={context.context}
            className="fill-gray-900 dark:fill-gray-900"
            width={12}
            height={6}
          />
        )}
      </div>
    </FloatingPortal>
  )
})
TooltipAdvancedContent.displayName = "TooltipAdvancedContent"

export const TooltipAdvancedProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <>{children}</>
}
