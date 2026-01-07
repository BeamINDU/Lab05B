// src/mockData.js
export const products = [
    {
      productId: "001",
      productName: "CHASHU BELLY FDA. 1029",
      productWidth: 20,
      productHeight: 15,
      productLength: 30,
      productWeight: 25,
      isFragile: false,
      isStackable: true,
      isTop: false,
    },
    {
      productId: "002",
      productName: "WAGYU BEEF",
      productWidth: 25,
      productHeight: 20,
      productLength: 35,
      productWeight: 30,
      isFragile: true,
      isStackable: false,
      isTop: true,
    },
  ];
  
  export const pallets = [
    {
      palletId: "P001",
      palletCode: "PALLET-RED",
      palletname: "Pallet Red 100×120 cm.",
      palletwidth: 100,
      palletheight: 120,
      palletlength: 120,
      palletweight: 50,
      loadwidth: 100,
      loadheight: 120,
      loadlength: 120,
      loadweight: 1000,
    },
  ];
  
  export const containers = [
    {
      containerid: "C001",
      containercode: "CONTAINER-BLUE",
      containername: "Container Blue 500×400×300 cm.",
      containerwidth: 500,
      containerheight: 400,
      containerlength: 300,
      containerweight: 200,
      loadwidth: 490,
      loadheight: 390,
      loadlength: 290,
      loadweight: 5000,
    },
  ];
  
  export const simulate = [
    {
      simulateId: "SIM001",
      simulateType: "Pallet",
      status: "Pending",
      simulateBy: "User1",
      simulateDateTime: "2024-12-01T10:30:00",
      batches: [
        {
          batchId: "B001",
          palletId: "P001",
          containerid: null,
          products: [
            {
              productId: "001",
              qtt: 10,
              position: { x: 0, y: 0, z: 0 },
            },
            {
              productId: "002",
              qtt: 5,
              position: { x: 30, y: 0, z: 0 },
            },
          ],
        },
      ],
    },
  ];
  