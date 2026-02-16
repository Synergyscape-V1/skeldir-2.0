import type { Meta, StoryObj } from '@storybook/react';
import { MemoryRouter } from 'react-router-dom';
import { ForgeCommandCenter } from '../command-center/ForgeCommandCenter';
import { FIXTURES } from '../types';

const meta: Meta<typeof ForgeCommandCenter> = {
  title: 'A5-Forge/CommandCenter',
  component: ForgeCommandCenter,
  parameters: { layout: 'padded' },
  decorators: [(Story) => (<MemoryRouter><div className="max-w-7xl mx-auto"><Story /></div></MemoryRouter>)],
};
export default meta;
type Story = StoryObj<typeof ForgeCommandCenter>;
export const Ready: Story = { args: { initialState: FIXTURES.ready } };
export const Loading: Story = { args: { initialState: FIXTURES.loading } };
export const EmptyNoData: Story = { args: { initialState: FIXTURES.empty } };
export const EmptyBuildingModel: Story = { args: { initialState: FIXTURES.emptyBuildingModel } };
export const Error: Story = { args: { initialState: FIXTURES.error } };
