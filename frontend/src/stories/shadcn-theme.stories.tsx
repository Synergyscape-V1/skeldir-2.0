/**
 * D3.7 §6.2 — shadcn Theme Verification Story
 *
 * Proves that D0 token mapping is active by rendering multiple shadcn
 * primitives in both light and dark modes. Includes cases that verify:
 *   - Token mapping is active (colors match enterprise palette, not defaults)
 *   - Opacity modifiers behave correctly (hover/focus use alpha blending)
 *   - Focus rings are visible and correct
 *
 * Cursor workflow:
 *   Validate: `npm run storybook` → open "Theme / shadcn Theme Verification"
 *   Check: Toggle light/dark via toolbar. Focus rings visible on Tab.
 *   a11y panel: 0 critical violations.
 */

import type { Meta, StoryObj } from '@storybook/react-vite'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AlertCircle, CheckCircle2, Info } from 'lucide-react'

/* ------------------------------------------------------------------ */
/*  Theme Showcase Component                                           */
/* ------------------------------------------------------------------ */

function ShadcnThemeShowcase() {
  return (
    <div className="space-y-8 p-6 bg-background text-foreground min-h-screen">
      <h1 className="text-2xl font-bold">shadcn Theme Verification</h1>
      <p className="text-muted-foreground">
        All components below inherit D0 tokens via CSS variables. Toggle
        light/dark in the Storybook toolbar to verify both modes.
      </p>

      {/* ---- Buttons with opacity modifiers ---- */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Buttons (hover/focus states test opacity semantics)</h2>
        <div className="flex flex-wrap gap-3">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="destructive">Destructive</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          {/* Note: "link" variant not available in this shadcn config */}
        </div>
        <p className="text-xs text-muted-foreground">
          Tab through buttons to verify focus rings. Hover to verify opacity transitions.
        </p>
      </section>

      {/* ---- Inputs ---- */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Inputs</h2>
        <div className="grid gap-3 max-w-sm">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" placeholder="name@skeldir.io" />
          </div>
          <div>
            <Label htmlFor="disabled">Disabled</Label>
            <Input id="disabled" disabled placeholder="Disabled input" />
          </div>
        </div>
      </section>

      {/* ---- Select ---- */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Select</h2>
        <Select>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Select channel" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="stripe">Stripe</SelectItem>
            <SelectItem value="paypal">PayPal</SelectItem>
            <SelectItem value="square">Square</SelectItem>
          </SelectContent>
        </Select>
      </section>

      {/* ---- Badges ---- */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Badges</h2>
        <div className="flex flex-wrap gap-2">
          <Badge>Default</Badge>
          <Badge variant="secondary">Secondary</Badge>
          <Badge variant="destructive">Destructive</Badge>
          <Badge variant="outline">Outline</Badge>
        </div>
      </section>

      {/* ---- Alerts ---- */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Alerts</h2>
        <Alert>
          <Info className="h-4 w-4" />
          <AlertTitle>Information</AlertTitle>
          <AlertDescription>This is an informational alert using default variant.</AlertDescription>
        </Alert>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>This is a destructive alert. Check that destructive color maps to D0 error-500.</AlertDescription>
        </Alert>
      </section>

      {/* ---- Tabs ---- */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Tabs</h2>
        <Tabs defaultValue="overview">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="analytics">Analytics</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
          </TabsList>
          <TabsContent value="overview" className="p-4 border rounded-md">
            Overview content — verify background and border colors match D0 tokens.
          </TabsContent>
          <TabsContent value="analytics" className="p-4 border rounded-md">
            Analytics content.
          </TabsContent>
          <TabsContent value="settings" className="p-4 border rounded-md">
            Settings content.
          </TabsContent>
        </Tabs>
      </section>

      {/* ---- Dialog ---- */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Dialog</h2>
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline">Open Dialog</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Token Verification</DialogTitle>
              <DialogDescription>
                This dialog should use D0 background/foreground tokens.
                Check that overlay, border, and text colors are correct.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="name" className="text-right">Name</Label>
                <Input id="name" className="col-span-3" placeholder="Enter name" />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline">Cancel</Button>
              <Button>Confirm</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </section>

      {/* ---- Form validation states ---- */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Form Validation States</h2>
        <div className="grid gap-3 max-w-sm">
          <div>
            <Label htmlFor="valid" className="flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3 text-green-600" /> Valid Field
            </Label>
            <Input id="valid" defaultValue="valid@email.com" className="border-green-500 focus-visible:ring-green-500" />
          </div>
          <div>
            <Label htmlFor="invalid" className="text-destructive">Invalid Field</Label>
            <Input id="invalid" defaultValue="not-an-email" className="border-destructive focus-visible:ring-destructive" />
            <p className="text-sm text-destructive mt-1">Please enter a valid email address.</p>
          </div>
        </div>
      </section>

      {/* ---- Token color swatch reference ---- */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Token Color Swatches</h2>
        <div className="grid grid-cols-4 gap-2">
          {[
            ['--background', 'bg-background'],
            ['--foreground', 'bg-foreground'],
            ['--primary', 'bg-primary'],
            ['--secondary', 'bg-secondary'],
            ['--muted', 'bg-muted'],
            ['--accent', 'bg-accent'],
            ['--destructive', 'bg-destructive'],
            ['--border', 'bg-border'],
          ].map(([name, cls]) => (
            <div key={name} className="flex flex-col items-center gap-1">
              <div className={`w-12 h-12 rounded border ${cls}`} />
              <span className="text-xs text-muted-foreground">{name}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Story                                                              */
/* ------------------------------------------------------------------ */

const meta: Meta = {
  title: 'Theme/shadcn Theme Verification',
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component:
          'Comprehensive shadcn primitive showcase proving D0 token mapping ' +
          'is active, opacity modifiers work, and focus rings are correct.',
      },
    },
  },
  tags: ['autodocs'],
}

export default meta

type Story = StoryObj

export const LightMode: Story = {
  render: () => <ShadcnThemeShowcase />,
}
