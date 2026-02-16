import type { Meta, StoryObj } from '@storybook/react';
import { MemoryRouter } from 'react-router-dom';
import { PrismCommandCenter } from '../command-center/PrismCommandCenter';
import { FIXTURES } from '../types';

const meta: Meta<typeof PrismCommandCenter> = {
  title: 'A3-Prism/CommandCenter', component: PrismCommandCenter, parameters: { layout: 'padded' },
  decorators: [(Story) => (<MemoryRouter><div className="max-w-6xl mx-auto"><Story /></div></MemoryRouter>)],
};
export default meta;
type Story = StoryObj<typeof PrismCommandCenter>;
export const Ready: Story = { args: { initialState: FIXTURES.ready } };
export const Loading: Story = { args: { initialState: FIXTURES.loading } };
export const EmptyNoData: Story = { args: { initialState: FIXTURES.empty } };
export const EmptyBuildingModel: Story = { args: { initialState: FIXTURES.emptyBuildingModel } };
export const Error: Story = { args: { initialState: FIXTURES.error } };
