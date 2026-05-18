import { test, expect } from "@playwright/test";

test.describe("Solution Overview Section Validation", () => {
  test("Desktop: validate Solution Overview image section", async ({ page }) => {
    // Navigate to the page
    await page.goto("http://localhost:3099");
    
    // Wait for the page to be fully loaded
    await page.waitForLoadState("networkidle");
    
    // Find the Solution Overview section
    const solutionSection = page.locator("section.solution-overview-section").first();
    
    // Scroll to the section
    await solutionSection.scrollIntoViewIfNeeded();
    
    // Wait a moment for any lazy loading
    await page.waitForTimeout(1000);
    
    const solutionImage = solutionSection.locator("img.solution-overview-full");
    
    // 1. Validate image is visible and fully rendered
    await expect(solutionImage).toBeVisible();
    
    // Check that the image has loaded (naturalWidth > 0 means not broken)
    const imageLoaded = await solutionImage.evaluate((img: HTMLImageElement) => {
      return {
        complete: img.complete,
        naturalWidth: img.naturalWidth,
        naturalHeight: img.naturalHeight,
        currentSrc: img.currentSrc,
      };
    });
    
    console.log("Image load status:", imageLoaded);
    expect(imageLoaded.complete).toBe(true);
    expect(imageLoaded.naturalWidth).toBeGreaterThan(0);
    expect(imageLoaded.naturalHeight).toBeGreaterThan(0);
    
    // 2. Validate section order: Solution Overview → Problem articulation → Interactive Demo
    const sectionIndex = await page.evaluate(() => {
      const sections = Array.from(document.querySelectorAll("section"));
      const solutionIndex = sections.findIndex((s) => s.classList.contains("solution-overview-section"));
      const problemIndex = sections.findIndex((s) =>
        s.textContent?.includes("Why Your Current Attribution"),
      );
      const demoIndex = sections.findIndex((s) => s.textContent?.includes("Interactive Demo"));

      return { solutionIndex, problemIndex, demoIndex };
    });

    console.log("Section indices:", sectionIndex);
    expect(sectionIndex.solutionIndex).toBeGreaterThan(-1);
    expect(sectionIndex.problemIndex).toBeGreaterThan(-1);
    expect(sectionIndex.solutionIndex).toBeLessThan(sectionIndex.problemIndex);
    expect(sectionIndex.problemIndex).toBeLessThan(sectionIndex.demoIndex);
    
    // 3. Validate image is not clipped (check if image width matches container or is appropriately sized)
    const imageBox = await solutionImage.boundingBox();
    const containerBox = await solutionSection.boundingBox();
    
    console.log("Image dimensions:", imageBox);
    console.log("Container dimensions:", containerBox);
    
    if (imageBox && containerBox) {
      // Image should fit within container horizontally (with some padding tolerance)
      expect(imageBox.width).toBeLessThanOrEqual(containerBox.width + 10);
      // Image should not overflow on the sides
      expect(imageBox.x).toBeGreaterThanOrEqual(containerBox.x - 10);
      expect(imageBox.x + imageBox.width).toBeLessThanOrEqual(containerBox.x + containerBox.width + 10);
    }
    
    // 4. Take screenshot of the section
    await solutionSection.screenshot({ 
      path: "test-results/solution-overview-desktop.png",
      fullPage: false 
    });
    
    console.log("✓ Desktop screenshot saved to test-results/solution-overview-desktop.png");
  });

  test("Mobile (375px): validate Solution Overview image scales properly", async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    
    // Navigate to the page
    await page.goto("http://localhost:3099");
    
    // Wait for the page to be fully loaded
    await page.waitForLoadState("networkidle");
    
    // Find the Solution Overview section
    const solutionSection = page.locator("section.solution-overview-section").first();
    
    // Scroll to the section
    await solutionSection.scrollIntoViewIfNeeded();
    
    // Wait a moment for any lazy loading
    await page.waitForTimeout(1000);
    
    const mobilePipeline = solutionSection.locator(".solution-overview-mobile-pipeline");
    await expect(mobilePipeline).toBeVisible();
    const solutionImage = mobilePipeline.locator("img").first();

    // 5. Vertical pipeline: first stage (sources) visible and sized within viewport
    await expect(solutionImage).toBeVisible();

    const imageBox = await solutionImage.boundingBox();
    const containerBox = await solutionSection.boundingBox();
    const viewportWidth = 375;
    
    console.log("Mobile - Image dimensions:", imageBox);
    console.log("Mobile - Container dimensions:", containerBox);
    console.log("Mobile - Viewport width:", viewportWidth);
    
    if (imageBox && containerBox) {
      // Image should fit within mobile viewport (with padding tolerance)
      expect(imageBox.width).toBeLessThanOrEqual(viewportWidth);
      // Image should not overflow on the sides
      expect(imageBox.x).toBeGreaterThanOrEqual(-10); // Small negative tolerance for edge cases
      expect(imageBox.x + imageBox.width).toBeLessThanOrEqual(viewportWidth + 10);
    }
    
    // Check image properties on mobile
    const mobileImageStatus = await solutionImage.evaluate((img: HTMLImageElement) => {
      return {
        complete: img.complete,
        naturalWidth: img.naturalWidth,
        currentWidth: img.width,
        style: {
          width: img.style.width,
          maxWidth: img.style.maxWidth,
          objectFit: window.getComputedStyle(img).objectFit,
        },
      };
    });
    
    console.log("Mobile image status:", mobileImageStatus);
    expect(mobileImageStatus.complete).toBe(true);
    
    // 6. Take mobile screenshot
    await solutionSection.screenshot({ 
      path: "test-results/solution-overview-mobile-375.png",
      fullPage: false 
    });
    
    console.log("✓ Mobile screenshot saved to test-results/solution-overview-mobile-375.png");
  });
});
