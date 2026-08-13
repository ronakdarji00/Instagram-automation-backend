# Instagram Reels Comment Auto-Reply

Apne Instagram Business account ke reels par comments ka auto-reply bhejne wala simple Python script.

## Setup Steps

### 1. Meta Developer App banao
1. https://developers.facebook.com par jao → **My Apps** → **Create App**
2. App type: **Business** select karo
3. App banne ke baad **Add Product** → **Instagram** add karo

### 2. Permissions add karo
App settings me jaake ye permissions enable karo:
- `instagram_basic`
- `instagram_manage_comments`
- `pages_show_list`
- `pages_read_engagement`

### 3. Instagram Business account link karo
1. Apna Instagram account **Business** me convert karo (Instagram app → Settings → Account type and tools → Switch to Business)
2. Ek Facebook Page banao (agar already nahi hai)
3. Instagram account ko us Facebook Page se link karo
4. Meta Business Suite me jaake Page → Settings → Linked accounts → Instagram connect karo

### 4. Access token + IG User ID lo
Sabse asaan tarika — **Graph API Explorer** use karo:
1. https://developers.facebook.com/tools/explorer/ par jao
2. Apna Facebook Page select karo
3. "Generate Access Token" par click karo with permissions:
   - `instagram_basic`
   - `instagram_manage_comments`
   - `pages_read_engagement`
4. Page ID se IG Business Account ID nikaalo:
   ```
   GET /{page-id}?fields=instagram_business_account&access_token=...
   ```
   Response me `instagram_business_account.id` — ye tumhara `ig_user_id` hai

### 5. Long-lived token banao (recommended)
Short-lived token 1 hour me expire ho jata hai. Long-lived ke liye:
```
GET https://graph.facebook.com/v19.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={app_id}
  &client_secret={app_secret}
  &fb_exchange_token={short_lived_token}
```
Ye ~60 days valid rahega. Expiry se pehle refresh karna padega.

### 6. config.json bharo
```json
{
  "access_token": "tumhara_long_lived_token",
  "ig_user_id": "tumhara_ig_business_id",
  "reply_message": "Thanks for watching! 🙏",
  "state_file": "replied_comments.json",
  "max_comments_per_run": 50
}
```

## Run karna

```bash
pip install -r requirements.txt
python main.py            # ek baar run
python main.py --loop     # har 10 minute me repeat
python main.py --loop --interval 300   # har 5 minute
```

## Important Notes

- **Sirf apne account ke liye** use karna — dusre accounts pe spam mat karo
- Instagram ToS ke hisaab se **templated auto-replies** acceptable hain agar reasonable rate me ho
- `replied_comments.json` file me replied comment IDs save hote hain — dobara reply nahi hoga
- Token 60 din me expire hoga — uske baad refresh karo
- Agar rate limit hit ho jaye to `max_comments_per_run` kam kar do
- 24 ghante se purane comments ka reply API se generally nahi bhej paate — timely run karo

## Files

- `main.py` — main script
- `config.json` — tumhari settings
- `replied_comments.json` — auto-generated state file (isay delete mat karna warna duplicate replies honge)
- `requirements.txt` — Python dependencies
