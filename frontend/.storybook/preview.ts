import type { Preview } from "@storybook/react";
import "../src/styles/tokens.css";
import "../src/styles/app.css";
import "../src/stories/styles.css";

const preview: Preview = {
  parameters: {
    controls: { expanded: true },
    layout: "fullscreen",
    viewport: {
      viewports: {
        desktop1440: {
          name: "Desktop 1440",
          styles: { width: "1440px", height: "1024px" },
          type: "desktop",
        },
        tablet768: {
          name: "Tablet 768",
          styles: { width: "768px", height: "1024px" },
          type: "tablet",
        },
        mobile375: {
          name: "Mobile 375",
          styles: { width: "375px", height: "812px" },
          type: "mobile",
        },
      },
      defaultViewport: "desktop1440",
    },
  },
};

export default preview;
