# Cal.com redirect after booking (mobile)

For **redirect after booking** to work when users book from mobile (they are sent to the full Cal.com page), you must set the redirect URL **in your Cal.com event type**, not only in the link.

## Steps in Cal.com

1. Log in to [Cal.com](https://cal.com) and open **Event Types**.
2. Open the event type used for the demo (e.g. **Skeldir Demo**).
3. Find **Redirect after booking** (or similar) in the event type settings.
4. Enable it and set the redirect URL to your **thank-you page**:
   - Production: `https://YOUR_DOMAIN/book-demo/thank-you`
   - Example: `https://skeldir.com/book-demo/thank-you`
5. Save the event type.

After that, when a user completes a booking on the Cal.com page (e.g. from mobile), Cal.com will send them to `/book-demo/thank-you`, which shows a short confirmation and then redirects to the homepage.

## Thank-you page

The app already has a thank-you page at `/book-demo/thank-you` that:

- Shows: “You will receive a confirmation email shortly.”
- Offers a “Return to home” button.
- Auto-redirects to the homepage after 5 seconds.

No code changes are needed for the thank-you page; you only need to set the redirect URL in Cal.com as above.
