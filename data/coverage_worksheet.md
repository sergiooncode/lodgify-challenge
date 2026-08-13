# Coverage worksheet — calibrating recall

For each property, read the copy and tick which of the key facts it
**conveys**. A fact counts as conveyed if a reader would come away knowing
it — rephrasing is fine ("room for eight" conveys "sleeps 8"), but
implying something adjacent is not.

Write your answers into `data/coverage_labels.jsonl` using the rows in
`data/coverage_template.jsonl`: set `covered` to `true` or `false`.

The judge's own answers are not shown here on purpose.

---

## apartment_porto_sparse — v0

`generation_sha256: 0a4061c3922592df4031115fa4179661ab38bf71003f6a0ebf30514d36bad9c8`

### The copy

```
## HERO HEADLINE
Wake Up Steps from Porto's Historic Bolhão Market

## HIGHLIGHTS
- Cozy one-bedroom retreat in the heart of Porto
- Perfect for couples or solo travelers craving an authentic city escape
- Moments from the iconic Mercado do Bolhão and its buzzing food stalls
- Comfortable, private space to call your own after a day of exploring
- Stay connected with complimentary broadband internet

## ABOUT THIS PLACE
Tucked into one of Porto's most characterful neighborhoods, Apartamento Bolhão puts you right in the pulse of the city. Step outside and you're instantly swept into the sights, sounds, and aromas of the legendary Bolhão Market — think fresh fish, ripe fruit, fragrant bread, and the friendly chatter of local vendors. This is Porto living at its most genuine, and this apartment is your front-row seat to it all.

Designed for two, the space offers a relaxed, no-fuss base for your Porto adventure. Whether you're here to wander cobblestone streets, sip port wine along the Douro, or simply soak in the city's timeless charm, you'll return each evening to a comfortable, private nook where you can unwind, recharge, and plan tomorrow's discoveries.

With flexible check-in at 3 PM and check-out at 10 AM, your stay is structured to maximize your time exploring one of Europe's most beloved cities — all while having a warm, welcoming apartment to come home to.

## AMENITIES
- Broadband internet
- 1 bedroom, 1 bathroom
- Sleeps 2 guests
- Prime location near Mercado do Bolhão
```

### Facts — which does the copy convey?

0. located in Porto, Portugal
1. sleeps 2
2. 1 bedrooms
3. 1 bathrooms
4. check-in 3 PM, check-out 10 AM
5. has broadband internet

---

## villa_sitges — v0

`generation_sha256: e2dc40d547ff35f81345f5523cc1f3b9d89297a35dec2934a37d0f57f2e42408`

### The copy

```
# Casa Miramar

## HERO HEADLINE
Sun-Soaked Hillside Villa Above the Shimmering Shores of Sitges

## HIGHLIGHTS
- 🌊 Sweeping sea views from a peaceful hillside perch
- ☀️ South-facing terrace bathed in afternoon sun
- 🛏️ Sleeps 8 across 4 spacious bedrooms
- 🚗 Free on-site parking for two cars — rare in Sitges!
- 🏖️ Just a 5-minute stroll down to the beach
- ⭐ 4.72 average rating from 87 happy guests

## ABOUT THIS PLACE
Perched on the hills above Sitges, Casa Miramar offers the kind of view postcards are made of — the Mediterranean stretching out below, catching the light as the afternoon sun pours across your private terrace. This is a home built for lingering: for lazy breakfasts with a sea breeze, for glasses of local wine as the sky turns gold, for that soft, satisfying tiredness after a day at the beach.

Inside, four comfortable bedrooms and three full bathrooms give every guest their own space to unwind, while the open living room flows seamlessly onto the terrace — the kind of indoor-outdoor rhythm that makes a villa stay feel like a different way of life. The kitchen is fully equipped for everything from quick coffee to a proper home-cooked paella, and past guests rave about the thoughtful welcome touches, like a bottle of local wine waiting on arrival.

The beach is a scenic five-minute walk downhill (guests do note the climb back is a workout — consider it earned relaxation time!). Beyond that, the charm of Sitges itself awaits: cobblestone lanes, seaside cafés, and a coastal town that comes alive at golden hour.

With free parking for two cars, quiet residential surroundings, and air conditioning to keep things cool even in the height of August, Casa Miramar strikes the rare balance of tranquil retreat and easy access to everything that makes this coastal town special.

## AMENITIES
- 📶 Broadband internet
- ❄️ Air conditioning (bedrooms)
- 🍽️ Fully equipped kitchen with dishwasher
- 🛁 3 full bathrooms + laundry facilities
- 🚗 Free private parking (2 vehicles)
- 🌅 South-facing terrace with sea views
- 🛋️ Open-plan living room with terrace access

---
**Check-in:** 4:00 PM | **Check-out:** 11:00 AM
**Cancellation:** Free up to 14 days before arrival
**Payment:** 50% at booking, balance due 30 days before arrival
**Damage deposit:** €500, refunded within 7 days of checkout
```

### Facts — which does the copy convey?

0. located in Sitges, Spain
1. sleeps 8
2. 4 bedrooms
3. 3 bathrooms
4. check-in 4 PM, check-out 11 AM
5. has broadband internet
6. has dishwasher
7. has air conditioning
8. has bathroom and laundry facilities
9. has free parking on the premises
10. cancellation policy: Free cancellation up to 14 days before arrival.

---

## apartment_porto_sparse — v1

`generation_sha256: cace0a965dfdad7b300a7827d863fc7a99ed12e817ccf85add2161272d33799d`

### The copy

```
## HERO HEADLINE
Apartamento Bolhão – One-Bedroom Flat Near the Market in Porto

## HIGHLIGHTS
- One bedroom, sleeps 2
- One bathroom
- Located near the market in Porto
- Broadband internet available
- Check-in from 3 PM, check-out by 10 AM

## ABOUT THIS PLACE
Apartamento Bolhão is a one-bedroom flat in Porto, situated near the market. The apartment sleeps two guests and includes one bathroom. Check-in begins at 3 PM, and check-out is by 10 AM.

## AMENITIES
- Broadband internet
```

### Facts — which does the copy convey?

0. located in Porto, Portugal
1. sleeps 2
2. 1 bedrooms
3. 1 bathrooms
4. check-in 3 PM, check-out 10 AM
5. has broadband internet

---

## villa_sitges — v1

`generation_sha256: ca6aadc6fa81dcaf0aa106766df04be7d937d34e447d36138db5c912b849dd09`

### The copy

```
## HERO HEADLINE
Casa Miramar — Hillside Villa with Sea Views in Sitges

## HIGHLIGHTS
- Four bedrooms, three bathrooms, sleeps up to 8
- South-facing terrace that catches the afternoon sun
- Living room opens directly onto the terrace
- Parking for two cars on the property
- Fully equipped kitchen

## ABOUT THIS PLACE
Casa Miramar is a four-bedroom villa set on the hillside above town, with a south-facing terrace that catches the afternoon sun. The living room opens onto the terrace, connecting indoor and outdoor space. The kitchen is fully equipped, and parking is available for two cars on the property. Guests mention that the kitchen "had everything we needed" and note the air conditioning as "welcome in August." Another guest described the street as quiet, adding that they "slept well." Check-in is at 4 PM and check-out at 11 AM.

## AMENITIES
- Broadband internet
- Dishwasher
- Air conditioning
- Bathroom and laundry facilities
- Free parking on the premises
```

### Facts — which does the copy convey?

0. located in Sitges, Spain
1. sleeps 8
2. 4 bedrooms
3. 3 bathrooms
4. check-in 4 PM, check-out 11 AM
5. has broadband internet
6. has dishwasher
7. has air conditioning
8. has bathroom and laundry facilities
9. has free parking on the premises
10. cancellation policy: Free cancellation up to 14 days before arrival.

