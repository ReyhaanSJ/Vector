const { chromium, devices } = require('playwright');
(async () => {
  const [url, out] = [process.argv[2], process.argv[3]];
  const browser = await chromium.launch();
  const phone = devices['iPhone 15'] || devices['iPhone 14'] || devices['iPhone 13'];
  const ctx = await browser.newContext({ ...phone });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(url);
  await page.waitForFunction(() => document.getElementById('screen').naturalWidth > 0, null, { timeout: 8000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: out + '/phone-1-start.png' });
  // tap in the middle of the picture
  const box = await page.locator('#screen').boundingBox();
  await page.touchscreen.tap(box.x + box.width * 0.25, box.y + box.height * 0.5);
  await page.waitForTimeout(300);
  // drag up to scroll
  await page.mouse.move(box.x + 100, box.y + box.height * 0.8);
  await page.mouse.down(); await page.mouse.move(box.x + 100, box.y + box.height * 0.2, { steps: 8 }); await page.mouse.up();
  await page.waitForTimeout(300);
  await page.click('button[data-keys="enter"]');
  await page.fill('#ask', 'close calculator');
  await page.click('#send');
  await page.waitForSelector('.allow', { timeout: 5000 });
  await page.screenshot({ path: out + '/phone-2-asking.png' });
  await page.click('.allow');
  await page.waitForSelector('.bubble:not(.you)', { timeout: 5000 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: out + '/phone-3-reply.png' });
  await page.click('#bigBtn'); await page.waitForTimeout(500);
  await page.screenshot({ path: out + '/phone-4-big.png' });
  // a phone without the key
  const stranger = await (await browser.newContext({ ...phone })).newPage();
  await stranger.goto(url.split('?')[0]);
  await stranger.waitForTimeout(800);
  await stranger.screenshot({ path: out + '/phone-5-unpaired.png' });
  console.log(JSON.stringify({ errors }));
  await browser.close();
})();
