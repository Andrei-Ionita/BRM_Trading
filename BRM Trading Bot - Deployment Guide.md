# BRM Trading Bot - Deployment Guide

This guide will help you deploy the BRM Trading Bot in a production environment.

## 🚀 Quick Start

1. **Get Real Credentials**
   - Contact BRM operator to get your production credentials
   - Complete the conformance testing process
   - Sign the required legal documents

2. **Setup Environment**
   ```bash
   # Copy the production config template
   cp .env.production .env
   
   # Edit with your real credentials
   nano .env
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Test Connection**
   ```bash
   python3 test_real_auth.py
   ```

5. **Run the Bot**
   ```bash
   python3 production_bot.py
   ```

## 📋 Prerequisites

### 1. BRM Credentials
You need to obtain the following from the BRM operator:

- **Username/Client ID**: Your unique identifier
- **Password/Client Secret**: Your authentication secret
- **Portfolio ID**: Your trading portfolio identifier
- **Scope**: Usually `intraday_api`

### 2. Conformance Testing
Before production access:

- ✅ Pass the conformance test in the test environment
- ✅ Place and modify orders as required
- ✅ Submit conformance test documentation
- ✅ Get approval from BRM operator

### 3. Legal Documentation
Complete and sign:

- Trading agreement
- API access agreement
- Risk management documentation

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with your configuration:

```bash
# Environment
BRM_ENVIRONMENT=production  # or "test"

# Authentication
BRM_AUTH_METHOD=password    # or "basic"
BRM_USERNAME=your_username
BRM_PASSWORD=your_password
BRM_PORTFOLIO_ID=your_portfolio_id
BRM_SCOPE=intraday_api

# Trading Strategy
BRM_STRATEGY=manual         # manual, arbitrage, mean_reversion, momentum
BRM_AUTO_TRADING=false      # Enable automatic trading

# Risk Management
BRM_MAX_POSITION_SIZE=1000  # Maximum position size in MW
BRM_MAX_PRICE=10000         # Maximum price in cents/MWh
BRM_MIN_PRICE=-10000        # Minimum price in cents/MWh
BRM_RISK_LIMIT=50000        # Risk limit in EUR
```

### Trading Strategies

**Manual Trading** (`BRM_STRATEGY=manual`)
- No automatic trading
- Use API calls to place orders manually
- Full control over all trading decisions

**Simple Arbitrage** (`BRM_STRATEGY=arbitrage`)
- Identifies price differences between Day-Ahead and Intraday
- Automatically places orders when opportunities are found
- Requires `BRM_AUTO_TRADING=true`

**Mean Reversion** (`BRM_STRATEGY=mean_reversion`)
- Trades based on price deviations from historical averages
- Buys when prices are below average, sells when above
- Requires historical price data

**Momentum** (`BRM_STRATEGY=momentum`)
- Follows price trends and momentum indicators
- Trades in the direction of strong price movements
- Uses technical analysis indicators

## 🏃‍♂️ Running the Bot

### Development/Testing
```bash
# Test authentication
python3 test_real_auth.py

# Run demo (no real trading)
python3 demo.py

# Run with examples
python3 example_usage.py
```

### Production
```bash
# Run the production bot
python3 production_bot.py

# Run in background (Linux/Mac)
nohup python3 production_bot.py > bot.log 2>&1 &

# Run as a service (systemd)
sudo systemctl start brm-trading-bot
```

### Docker Deployment
```bash
# Build Docker image
docker build -t brm-trading-bot .

# Run container
docker run -d --name brm-bot --env-file .env brm-trading-bot
```

## 📊 Monitoring

### Logs
The bot creates detailed logs in:
- `brm_trading_bot.log` - Main log file
- Console output - Real-time status

### Key Metrics to Monitor
- **Authentication Status**: Token expiry and refresh
- **Connection Status**: WebSocket connectivity
- **Order Status**: Successful/failed orders
- **Position Status**: Current positions and P&L
- **Risk Metrics**: Exposure limits and violations

### Health Checks
```python
# Get bot status
status = bot.get_status()
print(status)

# Check positions
positions = bot.get_positions()
for pos in positions.values():
    print(f"{pos.contract_id}: {pos.quantity} MW @ €{pos.average_price:.2f}/MWh")

# Check active orders
orders = bot.get_active_orders()
print(f"Active orders: {len(orders)}")
```

## 🔒 Security Best Practices

### Credential Management
- ✅ Store credentials in environment variables or secure vault
- ✅ Never commit credentials to version control
- ✅ Use different credentials for test and production
- ✅ Rotate credentials regularly

### Network Security
- ✅ Use HTTPS/WSS connections only
- ✅ Implement firewall rules
- ✅ Monitor network traffic
- ✅ Use VPN for remote access

### Access Control
- ✅ Limit access to production systems
- ✅ Use role-based permissions
- ✅ Audit all trading activities
- ✅ Implement emergency stop procedures

## 🚨 Risk Management

### Position Limits
```python
# Set maximum position size
BRM_MAX_POSITION_SIZE=1000  # MW

# Set price limits
BRM_MAX_PRICE=10000   # 100 EUR/MWh in cents
BRM_MIN_PRICE=-10000  # -100 EUR/MWh in cents

# Set total risk limit
BRM_RISK_LIMIT=50000  # 50,000 EUR
```

### Emergency Procedures
1. **Stop Trading**: Set `BRM_AUTO_TRADING=false`
2. **Cancel Orders**: Use order management functions
3. **Close Positions**: Place offsetting orders
4. **Contact Support**: BRM operator emergency contact

### Monitoring Alerts
Set up alerts for:
- Large position changes
- Order rejections
- Connection failures
- Risk limit breaches
- Unusual market activity

## 🔧 Troubleshooting

### Common Issues

**Authentication Failures**
```bash
# Check credentials
echo $BRM_USERNAME
echo $BRM_PASSWORD

# Test authentication
python3 debug_auth.py
```

**Connection Issues**
```bash
# Check network connectivity
ping sso.test.brm-power.ro
ping intraday-pmd-api-ws-brm.test.nordpoolgroup.com

# Check firewall settings
telnet sso.test.brm-power.ro 443
```

**Order Rejections**
- Verify portfolio permissions
- Check contract availability
- Validate order parameters
- Review market hours

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python3 production_bot.py
```

### Support Contacts
- **BRM Technical Support**: [Contact from BRM documentation]
- **Nord Pool API Support**: idapi@nordpoolgroup.com
- **Emergency Trading Desk**: [Emergency contact from BRM]

## 📈 Performance Optimization

### System Requirements
- **CPU**: 2+ cores recommended
- **RAM**: 4GB+ recommended
- **Network**: Stable, low-latency connection
- **Storage**: 10GB+ for logs and data

### Optimization Tips
- Use SSD storage for better I/O performance
- Optimize network settings for low latency
- Monitor memory usage and garbage collection
- Use connection pooling for HTTP requests
- Implement efficient data structures for market data

## 🔄 Maintenance

### Regular Tasks
- **Daily**: Check logs and positions
- **Weekly**: Review trading performance
- **Monthly**: Update dependencies and security patches
- **Quarterly**: Review and update trading strategies

### Updates
```bash
# Update dependencies
pip install -r requirements.txt --upgrade

# Backup configuration
cp .env .env.backup

# Test updates in development first
BRM_ENVIRONMENT=test python3 production_bot.py
```

## 📞 Support

For technical issues:
1. Check this documentation
2. Review log files
3. Test in development environment
4. Contact BRM technical support
5. Contact Nord Pool API support if needed

Remember: Always test thoroughly in the test environment before deploying to production!
