# BRM API Order Placement Structure

## Key Findings from Swagger Documentation

### Block Orders Endpoint
- **URL**: `/api/v{version}/blockorders` (POST)
- **Content-Type**: `application/json`

### Block Order Structure
```json
{
  "blocks": [
    {
      "name": "SellProfitableBlock",
      "price": 50,
      "minimumAcceptanceRatio": 1,
      "linkedTo": null,
      "auctionId": null,
      "periods": [
        {
          "contractId": "NPIDA_1-20181101-01",
          "volume": -100
        },
        {
          "contractId": "NPIDA_1-20181101-02", 
          "volume": -150
        },
        {
          "contractId": "NPIDA_1-20181101-03",
          "volume": -130
        },
        {
          "contractId": "NPIDA_1-20181101-04",
          "volume": -100
        }
      ],
      "isSpreadBlock": false
    }
  ]
}
```

### Response Structure (201 Created)
```json
{
  "orderId": "00000000-0000-0000-0000-000000000000",
  "auctionId": null,
  "companyName": null,
  "portfolio": null,
  "areaCode": null,
  "modifier": null,
  "modified": "2001-01-01T00:00:00.000",
  "currencyCode": null,
  "comment": null,
  "blocks": [
    {
      "modifier": "ModifierName",
      "state": "Accepted",
      "name": "SellProfitableBlock",
      "price": 50,
      "minimumAcceptanceRatio": 1,
      "linkedTo": null,
      "exclusiveGroup": "ExclusiveGroupName",
      "periods": [
        {
          "contractId": "NPIDA_1-20181101-01",
          "volume": -100
        },
        {
          "contractId": "NPIDA_1-20181101-02",
          "volume": -150
        }
      ]
    }
  ]
}
```

### Key Requirements
1. **version** parameter is required in URL
2. **auctionId** should be specified (can be in block or as parameter)
3. **contractId** format appears to be area-specific (e.g., "NPIDA_1-20181101-01")
4. **volume** can be negative (sell) or positive (buy)
5. **price** is in EUR/MWh
6. **minimumAcceptanceRatio** controls partial fills (1 = all or nothing)

### Error Response (400 Bad Request)
```json
{
  "type": "string",
  "title": "string", 
  "status": 0,
  "detail": "string"
}
```

## Next Steps
1. Need to find CurveOrders endpoint structure for limit orders
2. Need to identify correct contractId format for Romanian market
3. Need to determine auctionId parameter usage
4. Test with actual BRM auction data
