type Product = {
  productid?: string;
  productcode: string;
  productname: string;
  productlength: number;
  productwidth: number;
  productheight: number;
  productweight: number;
  isfragile: boolean;
  issideup: boolean;
  istop: boolean;
  notstack: boolean;
  maxstack: number;
  create_date?: string;
  create_by?: string;
  update_date?: string;
  update_by?: string;
  qtt?: number;
  color: string;
  palletid?: string;  
  containerid?: number; 
};

type Container = {
  containerid: number | undefined;
  containercode: string;
  containername: string;
  color: string;
  containerwidth: number;
  containerheight: number;
  containerlength: number;
  containerweight: number;
  qtt: number;
  createby: string;
  loadwidth: number;
  loadheight: number;
  loadlength: number;
  loadweight: number;
  createdate?: string;
  updateby:string;
  updatedate:string;
  containersize:string;
};
type Pallet = {
  palletid: string;
  palletcode: string;
  palletname: string;
  color: string;
};
