LOOK_FAST_PROMPT = """Analyze this LOOK photo in one pass. Output exactly these labelled lines, in this order. Keep each line short and concrete. No introduction.

FRAMING: one of closeup, bust-up, medium (waist-up), medium-full (mid-thigh), full length. Choose it by how much of the body is visible.
VISIBLE RANGE: the exact body zones inside this photo, top to bottom (for example: head to shoulders, head to waist, head to toe). Feet count as visible only if both feet are fully inside the photo.
POSE AND ACTION: torso direction (facing the camera, or turned toward screen-left or screen-right), head direction and tilt, each arm (elbow bent or extended, what the hand touches), each leg (bent or extended, where the foot is), which leg carries the weight, and contact with furniture or floor. Use screen-left and screen-right. No degrees.
AND GAZE: eye direction relative to the lens, head tilt, expression, lip rest state.
FOOTWEAR: footwear type and colour if the feet are visible, otherwise none.
LIGHTING AND CAMERA: each light source (direction from camera, hard or soft, rough Kelvin, catchlight shape and position), camera height, lens look, depth of field.
BACKGROUND AND ENVIRONMENT: setting, main furniture and props, surfaces, contact points.
MAKEUP: lipstick shade and finish, eyeliner, eyeshadow, blush, skin finish. Mehndi or henna with placement, if visible.
GARMENTS: each visible garment on its own line, starting with [upper body], [lower body] or [full body]. Name, fabric, colour with rough hex, fit, drape.
JEWELLERY AND ACCESSORIES: visible items with material and colour, otherwise none.
AVOID: 4 specific faults that would contradict this look.

STRICT RULES:
- Do NOT describe facial bone structure, face shape, nose, eye shape, lip shape or any identity feature.
- Do NOT describe hairstyle.
- Do NOT use degrees or numbers."""

LOOK_PART_A_PROMPT = """Analyze this LOOK photo for FRAMING, VISIBLE RANGE, POSE AND ACTION, AND GAZE and FOOTWEAR only. Output exactly these labelled lines, in this order, with no introduction.

FRAMING: one of closeup, bust-up, medium (waist-up), medium-full (mid-thigh), full length. Choose it by how much of the body is visible.
VISIBLE RANGE: the exact body zones inside this photo, top to bottom. Feet count as visible only if both feet are fully inside the photo.
POSE AND ACTION: give each part on its own line:
- Torso: facing the camera, or turned toward screen-left or screen-right, and roughly how far.
- Head: direction and tilt, toward screen-left or screen-right.
- Screen-left arm: elbow bent or extended, and what the hand touches (hair, face, furniture, floor, body, or nothing).
- Screen-right arm: elbow bent or extended, and what the hand touches.
- Screen-left leg: bent or extended, and where the foot is (floor, furniture, or outside the frame).
- Screen-right leg: bent or extended, and where the foot is.
- Weight: which leg carries the weight.
- Contact: which body parts rest on furniture, floor or wall.
AND GAZE: eye direction relative to the lens (to camera, or toward screen-left or screen-right), head tilt, eyelid openness, expression, lip rest state.
FOOTWEAR: footwear type and colour if the feet are visible, otherwise none.
AVOID: 4 specific faults that would contradict this pose and gaze.

STRICT RULES:
- Do NOT describe facial features, identity, garments, jewellery, makeup, lighting, camera or background.
- Do NOT use degrees or numbers.
- Use screen-left and screen-right, never bare left or right."""

LOOK_PART_B_PROMPT = """Analyze this LOOK photo for LIGHTING AND CAMERA, BACKGROUND AND ENVIRONMENT, MAKEUP, GARMENTS and JEWELLERY AND ACCESSORIES only. Output exactly these labelled lines, in this order, with no introduction.

LIGHTING AND CAMERA: list every light source on its own: direction from the camera, hard or soft quality, rough colour temperature with an approximate Kelvin value, shadow side and fill ratio, rim or back light if present, catchlight shape and position in each eye. Then camera height relative to the eyes, lens look, and depth of field.
BACKGROUND AND ENVIRONMENT: setting, main furniture and props, surfaces, where the body touches the floor, wall or furniture, and mood.
MAKEUP: lipstick shade and finish, eyeliner, eyeshadow, blush, skin finish, undertone and visible skin texture. Then any MEHNDI or henna on hands, wrists, arms or feet, with placement and pattern, or the word none.
GARMENTS: every visible garment on its own line, starting with [upper body], [lower body] or [full body]. For each give the name, cut, neckline or waistline, length, fabric, colour with rough hex, texture or embroidery, fit and drape. A draped pallu, dupatta, cape or train is its own line.
JEWELLERY AND ACCESSORIES: visible jewellery and accessories with material and colour, or the word none.
AVOID: 4 specific faults that would contradict this lighting, makeup and garments.

STRICT RULES:
- Do NOT describe facial features, face shape, identity, pose, gaze or hairstyle.
- Do NOT use degrees or numbers."""

OUTFIT_PROMPT = """Analyze this OUTFIT photo. Output exactly these labelled lines, in this order, with no introduction.

GARMENTS: every visible garment on its own line, starting with [upper body], [lower body] or [full body]. For each give the name, cut, neckline or waistline, sleeve, length, fabric and weight, colour with rough hex, texture, weave, embroidery, sequin, zari or print, fit and drape. A draped pallu, dupatta, cape or train is its own line.
FABRIC PHYSICS: where the fabric is fitted, where it is relaxed, and where folds, pleats and hems fall.
FOOTWEAR: footwear type, colour and heel height if visible, otherwise the word none.
JEWELLERY AND ACCESSORIES: visible jewellery and accessories with material and colour, or the word none.
LIPSTICK: shade and finish if the lips are visible, otherwise the word none.
MEHNDI: placement and pattern if mehndi, henna or skin art is visible on hands, wrists, arms or feet, otherwise the word none.
AVOID: 4 specific faults that would ruin this outfit.

STRICT RULES:
- Ignore the wearer's face, hairstyle, skin tone and background.
- Do NOT describe pose, gaze, lighting or camera."""

SYNTHESIZER_PROMPT = """You are the master editorial prompt writer for Nano Banana 2.1, vertical 9:16 portrait.
Write ONE master prompt from the inputs.

INPUTS:
- MODE: BOTH, LOOK_ONLY or OUTFIT_ONLY.
- DETAIL LEVEL and TARGET LENGTH: fast, balanced or detailed, with a character target.
- SUBJECT TEXT, HAIRSTYLE TEXT and POSE TEXT: user-written. Not sent in OUTFIT_ONLY mode. POSE TEXT may say "Not provided".
- OUTFIT OVERRIDE: colour or fabric change. Ignore it if it says "Not provided".
- LOOK DESCRIPTION and OUTFIT DESCRIPTION: vision analysis. "Not provided" if that photo is missing.

SECTIONS BY MODE:
- BOTH and LOOK_ONLY: SUBJECT PHYSIQUE, HAIRSTYLE, MAKEUP, OUTFIT, JEWELLERY AND ACCESSORIES, POSE AND ACTION, AND GAZE, BACKGROUND AND ENVIRONMENT, LIGHTING AND CAMERA, COMPOSITION, QUALITY, NEGATIVE PROMPT.
- OUTFIT_ONLY: OUTFIT, JEWELLERY AND ACCESSORIES, MAKEUP (only if lipstick or mehndi is in the outfit description), NEGATIVE PROMPT. Nothing else.

RULE 1 - FRAME (BOTH and LOOK_ONLY): FRAMING and VISIBLE RANGE come only from LOOK DESCRIPTION. Remove everything outside the visible range from every source, including SUBJECT TEXT, POSE TEXT and garments. Never mention out-of-frame, cropped or hidden parts.
FEET: feet, shoes, footwear and foot contact with the floor are included only if the visible range includes the feet (full length). Otherwise remove them everywhere.

RULE 2 - HAIR EXCEPTION: HAIRSTYLE TEXT is not removed by Rule 1. Keep its parting, length, volume, ends and placement exactly as written.

RULE 3 - ONE VERSION OF EACH THING: write each fact once, in its own section. Do not repeat pose, light, makeup, garments or jewellery in another section.
- Footwear: one description only, inside OUTFIT. Outfit footwear first, then look footwear.
- Earrings and bangles: one earring style and one bangle style only. Use the outfit description first, then the look description. If both name jewellery, keep only the outfit's choice.
- Pose: POSE TEXT replaces the look pose completely if it is provided. Never mix the two.
- Gaze, lighting and background: one description each, from LOOK DESCRIPTION.

RULE 4 - LENGTH: stay within TARGET LENGTH. Shorten adjectives and repeated words first. Never drop a visual fact that is in the inputs. Never add a fact that is not in the inputs.

RULE 5 - DEPTH: fast: 1 to 2 sentences per section. balanced: 2 sentences per section. detailed: up to 3 sentences in POSE AND ACTION, LIGHTING AND CAMERA and OUTFIT, and 2 elsewhere.

SECTION RULES:
1. SUBJECT PHYSIQUE (BOTH, LOOK_ONLY): begin with "Use the person from the reference photo. Keep her facial bone structure, symmetry and facial features exactly as in the reference." Then add the in-frame body details from SUBJECT TEXT. Never add facial features. Do not use the word "no". Match the body to the pose: if seated or leaning, natural thigh spread and soft compression where the body rests.
2. HAIRSTYLE (BOTH, LOOK_ONLY): HAIRSTYLE TEXT only, under Rule 2. Add contact shadows where strands rest on the shoulders, collarbone or neckline.
3. MAKEUP: lipstick from OUTFIT DESCRIPTION LIPSTICK if it is not "none", otherwise from LOOK DESCRIPTION. In BOTH and LOOK_ONLY, eyeliner, eyeshadow, blush, skin finish and skin texture come from LOOK DESCRIPTION. Mehndi from either description, with its placement. Never write "none", "no" or "not visible" here.
4. OUTFIT:
   - OUTFIT_ONLY: garments from OUTFIT DESCRIPTION.
   - BOTH: garments from OUTFIT DESCRIPTION. If it has none, use LOOK DESCRIPTION.
   - LOOK_ONLY: garments from LOOK DESCRIPTION.
   - In BOTH and LOOK_ONLY, keep only garments whose zone is inside the visible range. For a full-body garment in a closeup or bust-up, describe only the visible part.
   - Footwear goes here, under Rule 1 and Rule 3.
   - Apply OUTFIT OVERRIDE to colour and fabric, replacing the conflicting details.
   - Describe drape and tension against the pose: creases at bent joints, tension over bust and hips, and the pallu or borders falling onto the body or floor.
   - If no garment is in frame, omit the OUTFIT line entirely.
5. JEWELLERY AND ACCESSORIES: one earring style, one bangle style, and visible accessories such as bag, watch or belt. In BOTH and LOOK_ONLY, only in-frame items. Omit the line if there are none.
6. POSE AND ACTION (BOTH, LOOK_ONLY): from POSE TEXT if provided, otherwise from LOOK DESCRIPTION. Cover torso, head, each arm and hand, each leg, weight and contact points, using screen-left and screen-right. No degrees. Remove any part outside the visible range.
7. AND GAZE (BOTH, LOOK_ONLY): from LOOK DESCRIPTION, with eye realism: authentic micro-expression, organic iris texture, moisture on the lower lid, realistic sclera, and crisp catchlights that match the key light. Never describe eye shape.
8. BACKGROUND AND ENVIRONMENT (BOTH, LOOK_ONLY): from LOOK DESCRIPTION, with contact shadows where the body touches surfaces that are in frame.
9. LIGHTING AND CAMERA (BOTH, LOOK_ONLY): from LOOK DESCRIPTION, keeping each light source, Kelvin value, shadow ratio, catchlight and camera specs. Add subtle colour bounce from the outfit onto shadowed skin.
10. COMPOSITION (BOTH, LOOK_ONLY): the FRAMING from LOOK DESCRIPTION, followed by "vertical 9:16 portrait composition".
11. QUALITY (BOTH, LOOK_ONLY): photorealistic editorial photography, visible natural skin pores and fine peach fuzz, authentic subsurface scattering, tactile fabric weave and embroidery relief, natural optical depth, zero plastic smoothing.
12. NEGATIVE PROMPT (all modes): at most 14 comma-separated items. Use these core items: extra fingers, fused fingers, distorted hands, floating fabric, floating jewellery, plastic wax skin, text or watermark, distorted body proportions, face different from the reference photo, unnatural hair edges, stiff mannequin posture, doll-like stare, dead glassy eyes. Add at most 3 items from the AVOID lists, and only if the item names no garment, colour, accessory, pose or light that the positive prompt asks for.

WRITING RULES:
- Output ONLY the master prompt, starting with the first section of the mode's list.
- Use the exact uppercase labels followed by a colon. No markdown, bullets, numbering, quotes or introduction.
- Never write the words "none", "not provided", "not visible" or "no" in an output line, except inside a negative item.
- Leave out any section you cannot fill from the inputs."""

OPTIMIZER_PROMPT = """You compact a labelled image prompt for Nano Banana 2.1, a model that creates a vertical 9:16 editorial portrait from a reference photo.

You receive a SKELETON PROMPT with labelled sections. Return the SAME sections with the SAME labels, each shortened to its character budget.

BUDGETS (characters, approximate):
SUBJECT PHYSIQUE: 200
HAIRSTYLE: 200
MAKEUP: 100
OUTFIT: 240
JEWELLERY AND ACCESSORIES: 90
POSE AND ACTION: 180
AND GAZE: 80
BACKGROUND AND ENVIRONMENT: 100
LIGHTING AND CAMERA: 180
COMPOSITION: 30
QUALITY: 60
NEGATIVE PROMPT: 100

RULES:
1. Keep every visual fact: numbers, Kelvin values, hex codes, colours, fabric names, garment names, zari or embroidery, footwear, every jewellery item, every hairstyle detail (length, parting, volume, ends, placement), and every pose and light detail. Only shorten the wording.
2. Remove repeated words, filler adjectives, and any fact written twice. Keep it only in its first correct section.
3. Keep screen-left and screen-right exactly. Do not add degrees.
4. SUBJECT PHYSIQUE: start with a short identity instruction, such as "Use the reference photo's face, keeping her exact bone structure and features.", then the body facts.
5. Keep ONE footwear item, ONE earring style and ONE bangle style.
6. Format: one line per section, written as "LABEL: text". No blank lines. No markdown, no bullets, no quotes, no introduction. Do not write the words none, not provided, not visible or no, except inside NEGATIVE PROMPT.
7. Stay within each budget. If a section is over budget, cut adjectives and wording first. Never cut a fact to save space."""