        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self.basic_auth
        }
        
        data = {
            "grant_type": self.grant_type,
            "scope": self.scope,
            "username": self.username,
            "password": self.password
        }
        
        try:
            logger.info("Requesting new access token...")
            
            response = requests.post(
                self.token_url, 
                headers=headers, 
                data=data, 
                verify=False,
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
                logger.info(f"Access token obtained, expires at {self.token_expires_at}")
                return self.access_token
            else:
                logger.error(f"Token request failed: {response.status_code} - {response.text}")